# -*- coding: utf-8 -*-
"""vidx MCP server（stdio JSON-RPC）。

DSH 侧通过 @deepseek-ai/dsh-mcp-client 以 stdio 拉起：
    <python> -m vidx.mcp_server   (cwd = video-plugin/engine, PYTHONPATH 同步设置)

工具（暴露为 mcp__video__<name>）：
    open(index...) -> 结构/元数据/索引状态
    index         -> 提交后台索引任务，立即返回 task_id
    status        -> 轮询任务 / 查索引状态（可长轮询）
    outline       -> 低 token 目录（平台章节/分P 或 ASR 自动分段）
    read          -> 指定时间段：字幕原文 + 关键帧图片（≤6 张）
    search        -> 字幕模糊检索 → 时间戳命中
    transcript    -> 整段/区间全文（用于全文总结）

stdout 只写 JSON-RPC 帧；日志一律走 stderr。
"""
from __future__ import annotations

import base64
import json
import sys
import traceback
from pathlib import Path

from . import pipeline, store, tasks, transcript

SERVER_INFO = {"name": "vidx", "version": "0.1.0"}
PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
MAX_IMAGES = 6


def _log(msg: str) -> None:
    try:
        print(f"[vidx-mcp] {msg}", file=sys.stderr, flush=True)
    except Exception:
        pass


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


_S = "string"
_N = "number"
_I = "integer"
_B = "boolean"

TOOLS = [
    {
        "name": "open",
        "description": (
            "解析一个视频来源（bilibili URL/BV 或本地文件路径），返回标题/时长/简介/分P/"
            "平台章节/字幕与音轨/当前索引状态。不会下载或建索引；下一步用 index。"
            "支持 BV 号、https://www.bilibili.com/video/BV...、本地 mp4/mkv 等。"
        ),
        "inputSchema": _schema({"source": {"type": _S, "description": "bilibili URL/BV 或本地视频绝对路径"}},
                               ["source"]),
    },
    {
        "name": "index",
        "description": (
            "提交“建立/补齐索引”的后台任务：bilibili 时下载音频/视频，字幕则直接用，"
            "无字幕则本地 faster-whisper ASR，再做场景切分+故事板关键帧。"
            "立即返回 task_id；用 status 轮询（status 支持 wait_s 长轮询）。"
            "长视频首次约 2–8 分钟；重复调用幂等（已就绪则秒回）。"
        ),
        "inputSchema": _schema({
            "source": {"type": _S, "description": "来源（URL/BV/本地路径）；与 video_id 二选一"},
            "video_id": {"type": _S, "description": "已 open 过的 video_id；与 source 二选一"},
            "asr": {"type": _S, "enum": ["auto", "on", "off"], "description": "auto=无字幕才 ASR（默认）"},
            "video": {"type": _S, "enum": ["auto", "full", "none"],
                      "description": "bilibili：full=下载整片（场景检测，默认）；none=只下音频"},
            "language": {"type": _S, "description": "ASR 语言：zh/en/fr；留空自动检测"},
            "frames": {"type": _I, "description": "故事板帧数上限（默认 60）"},
            "danmaku": {"type": _B, "description": "是否抓弹幕（可选）"},
            "force": {"type": _B, "description": "强制重跑（默认 false）"},
        }, []),
    },
    {
        "name": "status",
        "description": (
            "轮询 index 任务：传 task_id（可 wait_s 长轮询，默认 0 立即返回，最大 120）。"
            "也可传 video_id 查索引状态；都不传则列出最近任务。"
        ),
        "inputSchema": _schema({
            "task_id": {"type": _S},
            "video_id": {"type": _S},
            "wait_s": {"type": _N, "description": "长轮询秒数（0–120）"},
        }, []),
    },
    {
        "name": "outline",
        "description": (
            "返回低成本“目录”：平台章节（bilibili view_points）或按静音/长度自动分段，"
            "每段给 start/end/标题提示/首句/关键词。先看这个，再决定 read 哪些段。"
        ),
        "inputSchema": _schema({
            "video_id": {"type": _S},
            "detail": {"type": _S, "enum": ["brief", "normal"], "description": "brief 更省 token"},
        }, ["video_id"]),
    },
    {
        "name": "read",
        "description": (
            "精读一个时间段：返回该段字幕原文（带 mm:ss 时间戳）+ 该段关键帧图片（默认 4 张，最多 6）。"
            "t0/t1 接受秒数或 'mm:ss'。回答用户问题时引用这些时间戳与画面。"
        ),
        "inputSchema": _schema({
            "video_id": {"type": _S},
            "t0": {"type": _N, "description": "起始秒或 'mm:ss' 字符串"},
            "t1": {"type": _N, "description": "结束秒或 'mm:ss' 字符串"},
            "frames": {"type": _I, "description": "帧数 0–6，默认 4"},
        }, ["video_id", "t0", "t1"]),
    },
    {
        "name": "search",
        "description": (
            "在已索引视频的字幕里做模糊检索（中英文词/bigram，命中带词级 anchor）；"
            "中文自动加拼音同音回退（解决 ASR 把“王虹”写成王红/王洪/王宏 这类问题），"
            "并额外命中标题/标签/简介（match=metadata）。用户说“哪里提到 X / 那段关于 Y 的”时用。"
        ),
        "inputSchema": _schema({
            "video_id": {"type": _S},
            "query": {"type": _S},
            "k": {"type": _I, "description": "返回条数，默认 8"},
        }, ["video_id", "query"]),
    },
    {
        "name": "collection",
        "description": (
            "合集/分P 概览：列出该视频所有分P的标题/时长/是否已索引，已索引的分P附章节目录。"
            "用户问“这个合集/多P视频都讲了什么”“第二P是什么”时先用它。"
        ),
        "inputSchema": _schema({
            "source": {"type": _S, "description": "bilibili URL/BV 或缓存 video_id"},
        }, ["source"]),
    },
    {
        "name": "danmaku",
        "description": (
            "读取弹幕（可选开关，默认关闭）：index(danmaku=true) 或本工具 refresh=true 才会抓取/缓存。"
            "给时间区间时返回该区间的弹幕样本与密度（观众反应、高能点），不给则全片采样。"
        ),
        "inputSchema": _schema({
            "video_id": {"type": _S},
            "t0": {"type": _N, "description": "起始秒或 'mm:ss'"},
            "t1": {"type": _N, "description": "结束秒或 'mm:ss'"},
            "k": {"type": _I, "description": "返回条数，默认 20"},
            "refresh": {"type": _B, "description": "true=抓取/补齐弹幕（仅 bilibili）"},
        }, ["video_id"]),
    },
    {
        "name": "transcript",
        "description": (
            "返回整段或指定区间的字幕全文（纯文本+时间戳）。用户要“总结整个视频/全文要点”时用；"
            "75 分钟视频约 1.3 万 token，必要时先用 outline 再分段读。"
        ),
        "inputSchema": _schema({
            "video_id": {"type": _S},
            "t0": {"type": _N},
            "t1": {"type": _N},
            "max_chars": {"type": _I, "description": "截断长度（默认不截断）"},
        }, ["video_id"]),
    },
]


# ---------------- 结果渲染 ----------------

def _text(obj) -> dict:
    return {"type": "text", "text": json.dumps(obj, ensure_ascii=False)}


def _image_block(path: str) -> dict | None:
    p = Path(path)
    if not p.is_file():
        return None
    data = p.read_bytes()
    if len(data) > 8 * 1024 * 1024:
        return None
    return {"type": "image", "data": base64.b64encode(data).decode("ascii"),
            "mimeType": "image/png"}


def _with_images(text_obj: dict, paths: list[str]) -> list[dict]:
    content = [_text(text_obj)]
    for p in paths[:MAX_IMAGES]:
        blk = _image_block(p)
        if blk:
            content.append(blk)
    return content


def _strip_words(seg: dict) -> dict:
    """词级时间戳只用于检索锚点，别让 MCP 输出膨胀（存储里仍保留）。"""
    if isinstance(seg, dict) and "words" in seg:
        return {k: v for k, v in seg.items() if k != "words"}
    return seg


# ---------------- 参数辅助 ----------------

def _parse_time(v) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if ":" not in s:
        return float(s)
    out = 0.0
    for part in s.split(":"):
        out = out * 60 + float(part)
    return out


def _require_video(args: dict) -> str:
    vid = args.get("video_id") or args.get("source")
    if not vid:
        raise ValueError("需要 video_id（或先 open 拿 video_id）")
    s = str(vid).strip()
    if s.startswith("local_") or s.startswith("bili_"):
        return s
    # 容忍直接传 source：open 一下拿 video_id
    return pipeline.open_video(s)["meta"]["video_id"]


# ---------------- 方法分发 ----------------

def call_tool(name: str, args: dict) -> dict:
    if name == "open":
        res = pipeline.open_video(str(args["source"]))
        return {"content": [_text(res)]}

    if name == "index":
        if args.get("video_id"):
            source = str(args["video_id"])
        elif args.get("source"):
            source = str(args["source"])
        else:
            raise ValueError("index 需要 source 或 video_id")
        opts = {k: args[k] for k in ("asr", "video", "language", "frames", "danmaku", "force")
                if args.get(k) is not None}
        label = str(args.get("source") or args.get("video_id"))

        def fn(progress):
            return pipeline.index_video(source, opts, progress=progress)

        task_id = tasks.TASKS.start("index", label, fn)
        return {"content": [_text({
            "task_id": task_id, "status": "running",
            "hint": "调用 status(task_id, wait_s=60) 轮询；完成后 outline/read/search",
        })]}

    if name == "status":
        if args.get("task_id"):
            wait_s = min(120.0, max(0.0, float(args.get("wait_s") or 0)))
            t = tasks.TASKS.wait(str(args["task_id"]), timeout_s=wait_s) if wait_s > 0 \
                else tasks.TASKS.get(str(args["task_id"]))
            if not t:
                return {"content": [_text({"error": "未知 task_id"})], "isError": True}
            t = dict(t)
            t["log"] = (t.get("log") or [])[-6:]
            if t.get("status") == "completed":
                t["result"] = t.get("result")
            return {"content": [_text(t)]}
        if args.get("video_id"):
            vid = str(args["video_id"])
            meta = store.load_meta(vid)
            if not meta:
                return {"content": [_text({"error": f"缓存中没有 {vid}"})], "isError": True}
            return {"content": [_text({"meta": pipeline._trim_meta(meta),
                                       "index": pipeline.index_status(meta)})]}
        return {"content": [_text({"tasks": tasks.TASKS.list()})]}

    if name == "collection":
        src = args.get("source") or args.get("video_id")
        if not src:
            raise ValueError("collection 需要 source（URL/BV 或 video_id）")
        return {"content": [_text(pipeline.collection(str(src)))]}

    if name == "outline":
        return {"content": [_text(pipeline.outline(str(args["video_id"]),
                                                  detail=str(args.get("detail") or "normal")))]}

    if name == "read":
        vid = str(args["video_id"])
        res = pipeline.read(vid, _parse_time(args["t0"]), _parse_time(args["t1"]),
                           frames=args.get("frames"))
        frame_paths = [f["path"] for f in res.get("frames") or [] if f.get("path")]
        slim = dict(res)
        slim["segments"] = [_strip_words(s) for s in res.get("segments") or []]
        slim["frames"] = [{"t": f.get("t"), "path": f.get("path"), "reused": f.get("reused")}
                          for f in res.get("frames") or [] if f.get("path")]
        return {"content": _with_images(slim, frame_paths)}

    if name == "search":
        res = pipeline.search(str(args["video_id"]), str(args["query"]),
                             k=int(args.get("k") or 8))
        return {"content": [_text(res)]}

    if name == "danmaku":
        vid = str(args["video_id"])
        if args.get("refresh"):
            pipeline.ensure_danmaku(vid)
        t0 = _parse_time(args["t0"]) if args.get("t0") is not None else None
        t1 = _parse_time(args["t1"]) if args.get("t1") is not None else None
        res = pipeline.get_danmaku(vid, t0, t1, k=int(args.get("k") or 20))
        return {"content": [_text(res)]}

    if name == "transcript":
        t0 = _parse_time(args["t0"]) if args.get("t0") is not None else None
        t1 = _parse_time(args["t1"]) if args.get("t1") is not None else None
        res = pipeline.get_transcript(str(args["video_id"]), t0, t1)
        res["segments"] = [_strip_words(s) for s in res.get("segments") or []]
        max_chars = args.get("max_chars")
        if max_chars and len(res.get("text") or "") > int(max_chars):
            res["text"] = res["text"][: int(max_chars)] + "…"
            res["truncated"] = True
        return {"content": [_text(res)]}

    raise KeyError(f"未知工具: {name}")


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")
    is_notification = "id" not in msg
    if method == "initialize":
        requested = (msg.get("params") or {}).get("protocolVersion")
        version = requested if requested in PROTOCOLS else PROTOCOLS[0]
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        try:
            result = call_tool(str(name), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as exc:  # noqa: BLE001
            _log("tool error: " + traceback.format_exc()[-1200:])
            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"error: {type(exc).__name__}: {exc}"}],
                "isError": True,
            }}
    if method in ("resources/list", "prompts/list", "logging/setLevel"):
        return {"jsonrpc": "2.0", "id": msg_id,
                "result": {"resources": []} if method == "resources/list" else {}}
    if is_notification:
        return None
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
    _log(f"started pid={__import__('os').getpid()} cwd={Path.cwd()}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            _log("bad json frame: " + line[:200])
            continue
        try:
            reply = handle(msg)
        except Exception:  # noqa: BLE001
            _log("handler crashed: " + traceback.format_exc()[-1200:])
            reply = {"jsonrpc": "2.0", "id": msg.get("id"),
                     "error": {"code": -32603, "message": "internal error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    _log("stdin closed, exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
