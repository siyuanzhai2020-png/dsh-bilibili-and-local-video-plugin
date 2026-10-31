# -*- coding: utf-8 -*-
"""面板数据接口（供 dsh-video-panel 的 host 路由调用）。

使用方式（host 侧 subprocess）::

    python -m vidx.panel_api list
    python -m vidx.panel_api detail '{"video_id": "..."}'
    python -m vidx.panel_api read   '{"video_id": "...", "t0": 0, "t1": 60, "frames": 4}'
    python -m vidx.panel_api search '{"video_id": "...", "query": "磁铁", "k": 8}'

所有命令输出单行 JSON（UTF-8），错误时输出 {"error": ...} 且退出码 1。
"""
from __future__ import annotations

import json
import shutil
import sys


def _seg(s: dict) -> dict:
    return {"t0": s.get("t0"), "t1": s.get("t1"), "text": s.get("text")}


def cmd_list(_args: dict) -> dict:
    from . import store
    summary = store.cache_summary()
    items = []
    for it in summary.get("items") or []:
        meta = store.load_meta(it["video_id"]) or {}
        idx = meta.get("index") or {}
        items.append({
            **it,
            "duration_s": meta.get("duration_s"),
            "source": (meta.get("source") or {}).get("kind"),
            "segments": idx.get("transcript_segments"),
            "shots": idx.get("shots"),
            "frames": idx.get("frames"),
            "danmaku": idx.get("danmaku"),
        })
    return {"root": summary.get("root"), "total_mb": summary.get("total_mb"),
            "trash_mb": summary.get("trash_mb"), "items": items}


def cmd_detail(args: dict) -> dict:
    from . import pipeline, store
    vid = str(args.get("video_id") or "")
    meta = store.load_meta(vid)
    if not meta:
        raise KeyError(f"缓存中没有 {vid}")
    out = pipeline.outline(meta["video_id"], detail="normal")
    doc = store.read_json(store.shots_path(meta["video_id"])) or {}
    frames = [{"t": f.get("t"), "file": f.get("path"), "shot": f.get("shot_idx")}
              for f in doc.get("storyboard") or []]
    shots = [{"idx": s.get("idx"), "t0": s.get("t0"), "t1": s.get("t1"),
              "dur": s.get("dur")} for s in (doc.get("shots") or [])]
    return {
        "video_id": meta["video_id"],
        "title": meta.get("title"),
        "duration_s": meta.get("duration_s"),
        "source": meta.get("source"),
        "index": pipeline.index_status(meta),
        "section_source": out.get("section_source"),
        "sections": out.get("sections") or [],
        "frames": frames,
        "shots": shots,
    }


def cmd_read(args: dict) -> dict:
    from . import pipeline
    vid = str(args.get("video_id") or "")
    t0 = float(args.get("t0") or 0)
    t1 = float(args.get("t1") or (t0 + 30))
    frames = int(args.get("frames") or 4)
    r = pipeline.read(vid, t0, t1, frames=frames)
    return {
        "video_id": r.get("video_id"),
        "range": r.get("range"),
        "segments": [_seg(s) for s in r.get("segments") or []],
        "frames": [{"t": f.get("t"), "file": f.get("path"), "reused": f.get("reused")}
                   for f in r.get("frames") or [] if f.get("path")],
        "shots": r.get("shots") or [],
    }


def cmd_search(args: dict) -> dict:
    from . import pipeline
    vid = str(args.get("video_id") or "")
    q = str(args.get("query") or "")
    k = int(args.get("k") or 8)
    r = pipeline.search(vid, q, k=k)
    hits = [{**h, "text": (h.get("text") or "")[:800]} for h in r.get("hits") or []]
    return {"video_id": r.get("video_id"), "query": q, "hits": hits,
            "searched_segments": r.get("searched_segments")}


def cmd_danmaku(args: dict) -> dict:
    from . import pipeline
    vid = str(args.get("video_id") or "")
    t0 = args.get("t0")
    t1 = args.get("t1")
    try:
        r = pipeline.get_danmaku(vid, float(t0) if t0 is not None else None,
                                 float(t1) if t1 is not None else None,
                                 k=int(args.get("k") or 20))
    except Exception as exc:  # 没有弹幕数据时返回空而不是报错
        return {"video_id": vid, "items": [], "count": 0, "error": str(exc)}
    return r


def cmd_delete(args: dict) -> dict:
    """删除一个视频的全部缓存（canonical 目录 + 其别名目录 + 别名表条目）。

    只动 `_video_cache`，不碰用户的原始视频文件。
    """
    from . import store
    raw = str(args.get("video_id") or "").strip()
    if not raw:
        raise ValueError("video_id 不能为空")
    vid = store.resolve_id(raw)
    root = store.cache_dir().resolve()
    names = {vid, raw}
    for alias, target in (store.load_aliases(force=True) or {}).items():
        if store.resolve_id(alias) == vid:
            names.add(alias)
    removed = []
    for name in sorted(names):
        d = store.raw_vdir(name)
        try:
            in_cache = root in d.resolve().parents
        except Exception:
            in_cache = False
        if in_cache and d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            removed.append(name)
    aliases = store.load_aliases(force=True) or {}
    kept = {a: c for a, c in aliases.items()
            if store.resolve_id(a) != vid and c != vid}
    if len(kept) != len(aliases):
        store.save_aliases(kept)
    if not removed:
        raise KeyError(f"缓存中没有 {raw}")
    return {"deleted": removed, "video_id": vid}


def cmd_clear(_args: dict) -> dict:
    """清空所有视频缓存（保留缓存根目录；原始视频文件不受影响）。"""
    from . import store
    root = store.cache_dir()
    removed = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        shutil.rmtree(child, ignore_errors=True)
        removed.append(child.name)
    trash = root / ".trash"
    if trash.is_dir():
        shutil.rmtree(trash, ignore_errors=True)
    store.save_aliases({})
    return {"deleted": removed, "count": len(removed)}


COMMANDS = {"list": cmd_list, "detail": cmd_detail, "read": cmd_read,
            "search": cmd_search, "danmaku": cmd_danmaku,
            "delete": cmd_delete, "clear": cmd_clear}


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except Exception:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        print(json.dumps({"error": f"用法: panel_api {{{'|'.join(COMMANDS)}}} [json]", }))
        return 2
    cmd, args = argv[0], {}
    if len(argv) > 1 and argv[1].strip():
        try:
            args = json.loads(argv[1])
        except Exception:
            print(json.dumps({"error": "第二个参数必须是 JSON"}))
            return 2
    try:
        result = COMMANDS[cmd](args)
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        return 0
    except Exception as exc:  # noqa: BLE001
        sys.stdout.write(json.dumps({"error": f"{type(exc).__name__}: {exc}"},
                                     ensure_ascii=False) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
