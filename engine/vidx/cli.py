# -*- coding: utf-8 -*-
"""vidx 命令行：M0 引擎自测入口（M1 起 MCP 也复用同一套 pipeline 函数）。

用法（在 engine/ 目录下）::

    python -m vidx.cli selftest
    python -m vidx.cli probe  path\to\video.mp4
    python -m vidx.cli open   "https://www.bilibili.com/video/BV..."
    python -m vidx.cli index  "<url or path>" [--no-asr] [--force] [--language zh]
    python -m vidx.cli status  <video_id>
    python -m vidx.cli outline <video_id> [--detail brief|normal]
    python -m vidx.cli read    <video_id> T0 T1 [--frames 4]
    python -m vidx.cli search  <video_id> "关键词" [-k 8]
    python -m vidx.cli transcript <video_id> [--srt out.srt]
    python -m vidx.cli cache
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

# 允许 python -m vidx.cli 从 engine/ 直接运行
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidx import media, pipeline, store, transcript  # noqa: E402
from vidx.config import load_config  # noqa: E402


def parse_time(s: str) -> float:
    s = str(s).strip()
    if ":" not in s:
        return float(s)
    parts = [float(x) for x in s.split(":")]
    v = 0.0
    for p in parts:
        v = v * 60 + p
    return v


def emit(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    ap = argparse.ArgumentParser(prog="vidx", description="视频阅读引擎 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_cache = sub.add_parser("cache", help="缓存占用 / LRU 清理 / 身份迁移")
    p_cache.add_argument("--prune", action="store_true", help="按 LRU 淘汰到 --cap-gb（默认 10GB）")
    p_cache.add_argument("--migrate", action="store_true",
                         help="合并同一视频的 local_*/bili_* 缓存（bvid 归一）")
    p_cache.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run 只出清单）")
    p_cache.add_argument("--cap-gb", type=float, default=None)
    sub.add_parser("selftest", help="ASR/ffmpeg/yt-dlp 环境自检")

    p_probe = sub.add_parser("probe", help="探测本地媒体文件")
    p_probe.add_argument("path")

    p_open = sub.add_parser("open", help="解析来源（本地/bilibili），拿元数据")
    p_open.add_argument("source")

    p_col = sub.add_parser("collection", help="合集/分P 概览（标题/时长/索引状态/章节）")
    p_col.add_argument("source")

    p_idx = sub.add_parser("index", help="建立索引（下载→字幕/ASR→场景→关键帧）")
    p_idx.add_argument("source")
    p_idx.add_argument("--asr", choices=["auto", "on", "off"], default="auto")
    p_idx.add_argument("--video", choices=["auto", "full", "none"], default="auto")
    p_idx.add_argument("--frames", type=int, default=None)
    p_idx.add_argument("--language", default=None)
    p_idx.add_argument("--danmaku", action="store_true", default=None,
                       help="抓取弹幕（默认关；config danmaku_default=true 可全局打开）")
    p_idx.add_argument("--force", action="store_true")
    p_idx.add_argument("--prefer-subtitle", default=None)
    p_idx.add_argument("--quiet", action="store_true")

    p_st = sub.add_parser("status")
    p_st.add_argument("video_id")

    p_ol = sub.add_parser("outline")
    p_ol.add_argument("video_id")
    p_ol.add_argument("--detail", choices=["brief", "normal"], default="normal")

    p_rd = sub.add_parser("read")
    p_rd.add_argument("video_id")
    p_rd.add_argument("t0")
    p_rd.add_argument("t1")
    p_rd.add_argument("--frames", type=int, default=None)

    p_se = sub.add_parser("search")
    p_se.add_argument("video_id")
    p_se.add_argument("query")
    p_se.add_argument("-k", type=int, default=8)

    p_tr = sub.add_parser("transcript")
    p_tr.add_argument("video_id")
    p_tr.add_argument("--srt", default=None)

    p_dm = sub.add_parser("danmaku", help="弹幕：抓取/读取（可选开关，默认关闭）")
    p_dm.add_argument("video_id")
    p_dm.add_argument("--fetch", action="store_true", help="抓取/补齐弹幕并缓存")
    p_dm.add_argument("--from", dest="t0", default=None, help="起始秒或 mm:ss")
    p_dm.add_argument("--to", dest="t1", default=None, help="结束秒或 mm:ss")
    p_dm.add_argument("--limit", type=int, default=20)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "cache":
            if args.migrate:
                emit(store.migrate_aliases(dry_run=not args.apply))
            elif args.prune:
                emit(store.cache_prune(
                    cap_gb=args.cap_gb or float(cfg.get("cache_cap_gb", 10.0)),
                    dry_run=not args.apply))
            else:
                emit(store.cache_summary())
        elif args.cmd == "selftest":
            emit(selftest(cfg))
        elif args.cmd == "probe":
            p = args.path
            info = media.probe_media(p)
            from vidx import sources
            info["sidecar_subtitles"] = sources.sidecar_subtitles(p)
            emit(info)
        elif args.cmd == "open":
            emit(pipeline.open_video(args.source, cfg))
        elif args.cmd == "collection":
            emit(pipeline.collection(args.source, cfg))
        elif args.cmd == "index":
            state = {"stage": None, "pct": -1.0}

            def progress(stage, pct, msg=""):
                # 节流：stage 变化或进度前进 ≥2% 才打印，避免 ASR 每段刷屏
                if args.quiet:
                    return
                advanced = pct >= state["pct"] + 0.02
                if stage != state["stage"] or advanced or pct >= 0.999:
                    state["stage"] = stage
                    state["pct"] = max(pct, state["pct"])
                    print(f"[{pct * 100:5.1f}%] {stage:14s} {msg}", file=sys.stderr, flush=True)
            opts = {"asr": args.asr, "video": args.video, "force": args.force,
                    "language": args.language, "danmaku": args.danmaku,
                    "prefer_subtitle": args.prefer_subtitle}
            if args.frames:
                opts["frames"] = args.frames
                cfg["storyboard_max"] = args.frames
            emit(pipeline.index_video(args.source, opts, progress=progress, cfg=cfg))
        elif args.cmd == "status":
            meta = store.load_meta(args.video_id)
            if not meta:
                emit({"error": f"缓存中没有 {args.video_id}"})
                return 2
            emit({"meta": pipeline._trim_meta(meta), "index": pipeline.index_status(meta)})
        elif args.cmd == "outline":
            emit(pipeline.outline(args.video_id, detail=args.detail, cfg=cfg))
        elif args.cmd == "read":
            emit(pipeline.read(args.video_id, parse_time(args.t0), parse_time(args.t1),
                               frames=args.frames, cfg=cfg))
        elif args.cmd == "search":
            emit(pipeline.search(args.video_id, args.query, k=args.k, cfg=cfg))
        elif args.cmd == "transcript":
            doc = pipeline.get_transcript(args.video_id, cfg=cfg)
            if args.srt:
                transcript.write_srt(doc["segments"], args.srt)
                doc["srt"] = args.srt
            emit(doc)
        elif args.cmd == "danmaku":
            if args.fetch:
                emit(pipeline.ensure_danmaku(args.video_id, cfg))
            else:
                t0 = parse_time(args.t0) if args.t0 else None
                t1 = parse_time(args.t1) if args.t1 else None
                emit(pipeline.get_danmaku(args.video_id, t0, t1,
                                          k=args.limit, cfg=cfg))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}",
                          "trace": traceback.format_exc()[-1500:]},
                         ensure_ascii=False, indent=1), file=sys.stderr)
        return 1


def selftest(cfg: dict) -> dict:
    out: dict = {"config": {k: cfg[k] for k in ("ffmpeg", "ytdlp", "model_dir", "cache_dir",
                                                 "device", "compute_type")}}
    # ffmpeg
    try:
        out["ffmpeg"] = {"ok": True, "path": media.ffmpeg_path()}
    except Exception as exc:
        out["ffmpeg"] = {"ok": False, "error": repr(exc)}
    # yt-dlp
    try:
        from vidx import sources
        out["ytdlp"] = {"ok": True, "path": sources._ytdlp(cfg)}
    except Exception as exc:
        out["ytdlp"] = {"ok": False, "error": repr(exc)}
    # ASR 探活（真实推理 probe）
    try:
        from vidx.asr import ASR
        asr = ASR(cfg=cfg, idle_unload_s=int(cfg.get("idle_unload_s", 600)))
        out["asr"] = asr.health()
        out["asr"]["model_dir"] = cfg.get("model_dir")
    except Exception as exc:
        out["asr"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    # gpu 摘要
    try:
        import subprocess
        cp = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used",
                             "--format=csv,noheader"], capture_output=True, text=True, timeout=15)
        out["gpu"] = cp.stdout.strip() if cp.returncode == 0 else "n/a"
    except Exception:
        out["gpu"] = "n/a"
    out["ok"] = all(out[k].get("ok") for k in ("ffmpeg", "ytdlp", "asr") if isinstance(out.get(k), dict))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
