# -*- coding: utf-8 -*-
"""编排层：open / index / outline / read / search（CLI 与 MCP 共用的唯一入口）。"""
from __future__ import annotations

import time
from pathlib import Path

from . import media, scenes, sources, store, transcript
from .config import load_config

DEFAULT_OPTIONS = {
    "asr": "auto",        # auto | on | off
    "video": "auto",      # auto | full | none（bilibili：none=只下音频，不建场景索引）
    "frames": None,       # 故事板帧数上限（None=配置默认）
    "force": False,       # 强制重跑
    "language": None,     # ASR 语言（None=自动）
    "danmaku": False,     # 抓弹幕（可选）
    "prefer_subtitle": None,  # 字幕语言偏好，如 zh/en
}


def _trim_meta(meta: dict) -> dict:
    """给工具/CLI 的精简 meta（不含完整 ffmpeg 探测与原始列表噪声）。"""
    probe = meta.get("media") or {}
    return {
        "video_id": meta["video_id"],
        "source": meta.get("source"),
        "title": meta.get("title"),
        "series_title": meta.get("series_title"),
        "duration_s": meta.get("duration_s"),
        "owner": meta.get("owner"),
        "tags": meta.get("tags") or [],
        "description": (meta.get("description") or "")[:600],
        "pages": meta.get("pages") or [],
        "platform_chapters": meta.get("platform_chapters") or [],
        "tracks": {
            "video": probe.get("video") or [],
            "audio": probe.get("audio") or [],
            "subtitle": probe.get("subtitle") or [],
            "sidecar_subtitles": meta.get("sidecar_subtitles") or [],
            "hdr": probe.get("hdr", False),
        },
        "index": meta.get("index") or {"status": "none"},
    }


def _resolve_meta(source_or_id: str, cfg: dict) -> dict:
    s = (source_or_id or "").strip()
    if s.startswith("local_") or s.startswith("bili_"):
        meta = store.load_meta(s)
        if not meta:
            raise KeyError(f"缓存中没有 {s}，请先 open/index")
        return meta
    return sources.open_source(s, cfg)


def _load_segments(video_id: str) -> list[dict]:
    return store.read_jsonl(store.transcript_path(video_id))


def _count_words(segments: list[dict]) -> int:
    total = 0
    for s in segments:
        t = s["text"]
        total += len(t.split()) if any(c.isascii() and c.isalpha() for c in t) else len(t)
    return total


def index_status(meta: dict) -> dict:
    idx = meta.get("index") or {}
    vdir = store.vdir(meta["video_id"])
    return {
        "status": idx.get("status", "none"),
        "transcript_source": idx.get("transcript_source"),
        "transcript_segments": idx.get("transcript_segments", 0),
        "frames": idx.get("frames", 0),
        "shots": idx.get("shots", 0),
        "danmaku": idx.get("danmaku", 0),
        "asr_language": idx.get("asr_language"),
        "video_cached": (vdir / "source").is_dir() and any(
            (vdir / "source").glob("full.*")),
        "timings": idx.get("timings"),
        "built_at": idx.get("built_at"),
        "dir": str(vdir),
    }


def open_video(source: str, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    meta = sources.open_source(source, cfg)
    store.touch(meta["video_id"])
    return {"meta": _trim_meta(meta), "index": index_status(meta),
            "next": "index(video_id) 建立索引后即可 outline/read/search"}


def _pick_local_media(meta: dict) -> str | None:
    """同 bvid 已有本地副本时优先复用（时长差 ≤2s），避免重复下载。"""
    src = meta.get("source") or {}
    cands = list(src.get("local_paths") or [])
    if src.get("kind") == "local" and src.get("path"):
        cands.append(src["path"])
    target = float(meta.get("duration_s") or 0)
    for c in cands:
        try:
            p = Path(c)
            if not p.is_file() or p.stat().st_size < 1024 * 1024:
                continue
            d = media.duration_of(str(p))
            if target and abs(d - target) > 2.0:
                continue
            return str(p.resolve())
        except Exception:
            continue
    return None


def _subtitle_tracks(meta: dict, video_id: str, video_path: str | None,
                     cfg: dict, progress) -> tuple[list[dict], str]:
    """收集可用字幕轨：内嵌 / 侧车 / bilibili CC（登录态）。"""
    tracks: list[dict] = []
    kind = meta["source"]["kind"]
    if video_path:
        probe = meta.get("media") or media.probe_media(video_path)
        tracks += sources.embedded_subtitles(video_id, video_path, probe, cfg, progress)
        for sc in sources.sidecar_subtitles(video_path):
            try:
                segs = transcript.load_subtitle_file(sc["path"])
            except Exception:
                continue
            if segs:
                tracks.append({"path": sc["path"], "kind": "sidecar",
                               "lang": sc.get("lang") or "", "segments": segs})
    # bilibili CC（匿名通常为空；有登录 cookie 时会有 subtitle_url）
    for st in meta.get("subtitle_tracks") or []:
        segs = sources.fetch_bili_subtitle_json(st, cfg)
        if segs:
            tracks.append({"path": "", "kind": "cc", "lang": st.get("lan") or "",
                           "segments": segs})
    return tracks, kind


def index_video(source_or_id: str, options: dict | None = None,
                progress=None, cfg: dict | None = None) -> dict:
    """建立/补齐索引。返回摘要 dict（JSON-safe）。"""
    cfg = cfg or load_config()
    opts = dict(DEFAULT_OPTIONS)
    opts.update(options or {})
    t_start = time.time()
    timings: dict = {}

    def emit(stage: str, pct: float, msg: str = "") -> None:
        if progress:
            progress(stage, pct, msg)

    meta = _resolve_meta(source_or_id, cfg)
    video_id = meta["video_id"]
    kind = meta["source"]["kind"]
    store.touch(video_id)
    emit("prepare", 0.02, f"准备 {meta.get('title') or video_id}")

    # 1) 取媒体
    video_path: str | None = None
    local_media = _pick_local_media(meta)
    if kind == "local":
        video_path = local_media or meta["source"]["path"]
        if not Path(video_path).is_file():
            raise FileNotFoundError(f"本地视频不存在（可能被移动）: {video_path}")
    else:
        bvid = meta["source"]["bvid"]
        page = int(meta["source"].get("page") or 1)
        if opts["video"] != "none":
            if local_media:
                video_path = local_media
                timings["media_reused"] = 1
                emit("probe", 0.05, f"复用本地副本（同 bvid）：{Path(local_media).name}")
            else:
                t0 = time.time()
                emit("download_video", 0.05, "下载视频（场景检测/抽帧用）")
                video_path = sources.ensure_bili_video(video_id, bvid, page, cfg, progress=progress)
                timings["download_video_s"] = round(time.time() - t0, 2)
        else:
            emit("download_audio", 0.05, "仅下载音频")
            t0 = time.time()
            sources.ensure_bili_audio(video_id, bvid, page, cfg, progress=progress)
            timings["download_audio_s"] = round(time.time() - t0, 2)

    # 2) 探测媒体
    probe = meta.get("media")
    if video_path and (opts["force"] or not probe or probe.get("path") != str(Path(video_path).resolve())):
        emit("probe", 0.08, "探测媒体信息")
        probe = media.probe_media(video_path)
    if probe:
        meta["media"] = probe
        if not meta.get("duration_s"):
            meta["duration_s"] = probe.get("duration_s")
    duration = float(meta.get("duration_s") or (probe or {}).get("duration_s") or 0)
    meta["video_cache_path"] = video_path

    # 3) 文本：字幕优先，缺失才 ASR
    need_text = opts["force"] or not store.transcript_path(video_id).is_file()
    if need_text:
        tracks, _ = _subtitle_tracks(meta, video_id, video_path, cfg, progress)
        pick = sources._pick_subtitle_track(tracks, opts.get("prefer_subtitle"))
        segments: list[dict] = []
        src_label = ""
        if pick:
            segments = pick["segments"]
            src_label = pick["kind"]
            emit("subtitles", 0.3, f"使用 {pick['kind']} 字幕 {len(segments)} 段")
        else:
            if opts["asr"] == "off":
                raise RuntimeError("没有可用字幕且 asr=off")
            emit("asr", 0.15, "无字幕，开始 ASR")
            t0 = time.time()
            wav = (sources.ensure_bili_audio(video_id, meta["source"]["bvid"],
                                             int(meta["source"].get("page") or 1), cfg) if kind == "bilibili"
                   else sources.ensure_local_audio(video_id, video_path, cfg))
            timings["audio_extract_s"] = round(time.time() - t0, 2)
            from .asr import ASR  # 延迟导入：asr.py 依赖 numpy/ctranslate2
            asr = ASR(cfg=cfg, language=opts.get("language") or None,
                      idle_unload_s=int(cfg.get("idle_unload_s", 600)))
            t0 = time.time()
            result = asr.transcribe(wav, language=opts.get("language") or None,
                                    progress=lambda done, total, text: emit(
                                        "asr", 0.15 + 0.35 * min(1.0, done / max(total, 1.0)),
                                        f"ASR {done:.0f}/{total:.0f}s {text[:40]}"))
            timings["asr_s"] = round(time.time() - t0, 2)
            raw_segments = result.get("segments") or []
            # 词级时间戳 -> 句/段级重分段（解决 ASR 超长段；无词数据则保留原段）
            reseg = transcript.resegment(
                raw_segments,
                max_s=float(cfg.get("resegment_max_s", 12.0)),
                min_s=float(cfg.get("resegment_min_s", 0.8)),
                pause_s=float(cfg.get("resegment_pause_s", 0.6)))
            segments = reseg or raw_segments
            src_label = "asr"
            idx = meta.setdefault("index", {})
            idx["asr_device"] = f"{result.get('device')}/{result.get('compute_type')}"
            idx["asr_language"] = result.get("language")
            idx["asr_model"] = result.get("model")
            idx["asr_rtf"] = round(float(result.get("rtf") or 0), 4)
            idx["asr_raw_segments"] = len(raw_segments)
            idx["asr_words"] = result.get("word_count") or 0
            idx["resegmented"] = bool(reseg)
            if reseg:
                store.write_jsonl(store.vdir(video_id) / "transcript.raw.jsonl", raw_segments)
            # 无视频时也能用音频时长回填
            if not duration:
                duration = float(result.get("duration_s") or 0)
                meta["duration_s"] = duration
        if not segments:
            raise RuntimeError("未能获得任何文本（字幕/ASR 均为空）")
        rows = [dict(s, src=src_label) for s in segments]
        store.write_jsonl(store.transcript_path(video_id), rows)
        transcript.write_srt(segments, str(store.vdir(video_id) / "transcript.srt"))
        meta.setdefault("index", {})["transcript_source"] = src_label
        meta["index"]["transcript_segments"] = len(rows)
        emit("subtitles", 0.55, f"文本就绪：{len(rows)} 段（{src_label}）")
    else:
        segments = _load_segments(video_id)
        idx = meta.setdefault("index", {})
        if not idx.get("transcript_source"):
            srcs = {str(r.get("src")) for r in segments if r.get("src")}
            idx["transcript_source"] = (srcs.pop() if len(srcs) == 1 else
                                        ("mixed" if srcs else "unknown"))
        idx["transcript_segments"] = len(segments)
        emit("subtitles", 0.55, f"复用已有文本：{len(segments)} 段")

    # 4) 视觉：场景切分 + 故事板
    scene_doc: dict | None = None
    if video_path:
        t0 = time.time()
        codec = ((probe or {}).get("video") or [{}])[0].get("codec")
        scene_doc = scenes.build_scene_index(
            video_path, video_id, cfg,
            progress=lambda st, pct, msg="": emit(st, 0.55 + 0.35 * pct, msg),
            force=opts["force"], codec=codec)
        timings["scenes_s"] = round(time.time() - t0, 2)
        meta.setdefault("index", {})["frames"] = len(scene_doc.get("storyboard") or [])
        meta["index"]["shots"] = (scene_doc.get("stats") or {}).get("shots", 0)
    else:
        timings["scenes_s"] = 0.0
        meta.setdefault("index", {})["frames"] = 0
        meta["index"]["shots"] = 0

    # 5) 弹幕（可选；默认关，config danmaku_default 或调用参数覆盖）
    want_dm = opts.get("danmaku")
    if want_dm is None:
        want_dm = bool(cfg.get("danmaku_default"))
    if want_dm and kind == "bilibili":
        cid = meta["source"].get("cid")
        if cid:
            t0 = time.time()
            dm = sources.fetch_danmaku(int(cid), cfg)
            if dm:
                store.write_jsonl(store.vdir(video_id) / "danmaku.jsonl", dm)
                idx = meta.setdefault("index", {})
                idx["danmaku"] = len(dm)
                idx["danmaku_at"] = store.now_iso()
                timings["danmaku_s"] = round(time.time() - t0, 2)

    # 6) 收尾
    idx = meta.setdefault("index", {})
    idx["status"] = "ready" if video_path else "text_only"
    idx["timings"] = {k: v for k, v in timings.items()}
    idx["built_at"] = store.now_iso()
    idx["pipeline_version"] = 1

    # 音频用完即删（默认；config.keep_audio=true 可保留以便重跑/调参）
    if not cfg.get("keep_audio"):
        removed = []
        for name in ("audio16k.wav", "audio.m4a"):
            p = store.source_dir(video_id) / name
            if p.is_file():
                try:
                    p.unlink()
                    removed.append(name)
                except OSError:
                    pass
        if removed:
            idx["audio_cleaned"] = removed

    store.save_meta(video_id, meta)
    timings["total_s"] = round(time.time() - t_start, 2)
    emit("done", 1.0, "索引完成")
    return {
        "video_id": video_id,
        "title": meta.get("title"),
        "duration_s": duration,
        "transcript": {"source": idx.get("transcript_source"),
                       "segments": idx.get("transcript_segments", 0),
                       "words": _count_words(segments),
                       "language": idx.get("asr_language")},
        "scenes": {"shots": idx.get("shots", 0), "frames": idx.get("frames", 0)},
        "timings": timings,
        "cache_dir": str(store.vdir(video_id)),
    }


def outline(video_id: str, detail: str = "normal", cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    meta = store.load_meta(video_id)
    if not meta:
        raise KeyError(f"缓存中没有 {video_id}")
    store.touch(meta["video_id"])
    segments = _load_segments(video_id)
    if not segments:
        raise RuntimeError("还没有文本索引，请先 index")
    duration = float(meta.get("duration_s") or (segments[-1]["t1"] if segments else 0))
    chapters = meta.get("platform_chapters") or []
    if len(chapters) >= 2:
        sections = transcript.sections_from_chapters(segments, chapters, duration)
        section_source = "platform"
    else:
        target = max(4, min(14, round(duration / 240) or 4))
        sections = transcript.auto_sections(segments, duration, target=target)
        section_source = "auto"
    if detail == "brief":
        sections = [{k: s[k] for k in ("idx", "t0", "t1", "title_hint") if k in s} for s in sections]
    return {
        "video_id": video_id,
        "title": meta.get("title"),
        "duration_s": duration,
        "owner": meta.get("owner"),
        "tags": (meta.get("tags") or [])[:10],
        "pages": meta.get("pages") or [],
        "section_source": section_source,
        "sections": sections,
        "transcript": {"source": (meta.get("index") or {}).get("transcript_source"),
                       "segments": len(segments)},
        "hint": "用 read(video_id, t0, t1) 精读某段；用 search 定位关键词",
    }


def collection(source_or_id: str, cfg: dict | None = None) -> dict:
    """合集/分P 概览：列出所有分P（标题/时长/是否已索引），已索引的附章节目录。"""
    cfg = cfg or load_config()
    meta = _resolve_meta(source_or_id, cfg)
    kind = (meta.get("source") or {}).get("kind")
    bvid = (meta.get("source") or {}).get("bvid") if kind == "bilibili" else None
    pages = meta.get("pages") or []
    if not pages:
        pages = [{"page": 1, "title": meta.get("title"), "duration_s": meta.get("duration_s")}]
    out_pages: list[dict] = []
    for p in pages:
        page_no = int(p.get("page") or 1)
        if kind == "bilibili" and bvid:
            vid = store.video_id_bili(bvid, page_no)
        else:
            vid = meta["video_id"]
        entry: dict = {
            "page": page_no,
            "title": p.get("title") or "",
            "duration_s": p.get("duration_s"),
            "video_id": vid,
            "url": (f"https://www.bilibili.com/video/{bvid}?p={page_no}"
                    if (kind == "bilibili" and bvid) else None),
            "indexed": False,
        }
        cm = store.load_meta(vid) if vid else None
        idx = (cm or {}).get("index") or {}
        if cm and idx.get("status") in ("ready", "text_only"):
            entry["indexed"] = True
            entry["index"] = {
                "status": idx.get("status"),
                "transcript_source": idx.get("transcript_source"),
                "transcript_segments": idx.get("transcript_segments"),
                "shots": idx.get("shots"), "frames": idx.get("frames"),
            }
            try:
                sub = outline(vid, detail="normal", cfg=cfg)
                entry["section_source"] = sub.get("section_source")
                secs = []
                for s in (sub.get("sections") or []):
                    hint = s.get("title_hint") or ""
                    kws = (s.get("keywords") or [])[:3]
                    label = hint if len(hint) >= 12 else " · ".join(kws)
                    secs.append({"idx": s.get("idx"), "t0": s.get("t0"), "t1": s.get("t1"),
                                 "label": label, "keywords": kws})
                entry["sections"] = secs
            except Exception:
                pass
        out_pages.append(entry)
    durations = [float(e.get("duration_s") or 0) for e in out_pages]
    return {
        "video_id": meta["video_id"],
        "series_title": meta.get("series_title") or meta.get("title"),
        "owner": meta.get("owner"),
        "kind": kind,
        "total_pages": len(out_pages),
        "indexed_pages": sum(1 for e in out_pages if e["indexed"]),
        "total_duration_s": round(sum(durations), 1),
        "pages": out_pages,
        "hint": ("对未索引分P用 index(source=<pages[].url>)；已索引分P用 outline/read/search"
                 "（传 pages[].video_id）"),
    }


def ensure_danmaku(video_id: str, cfg: dict | None = None) -> dict:
    """抓取/补齐弹幕（幂等：已有 danmaku.jsonl 直接返回）。"""
    cfg = cfg or load_config()
    meta = store.load_meta(video_id)
    if not meta:
        raise KeyError(f"缓存中没有 {video_id}")
    if (meta.get("source") or {}).get("kind") != "bilibili":
        raise RuntimeError("只有 bilibili 来源支持弹幕")
    path = store.vdir(video_id) / "danmaku.jsonl"
    rows = store.read_jsonl(path)
    if rows:
        return {"video_id": meta["video_id"], "count": len(rows), "cached": True,
                "path": str(path)}
    cid = meta["source"].get("cid")
    if not cid:
        raise RuntimeError("meta 里缺少 cid，无法抓弹幕")
    t0 = time.time()
    rows = sources.fetch_danmaku(int(cid), cfg)
    if not rows:
        raise RuntimeError("弹幕抓取为空（视频可能关闭弹幕，或接口变化）")
    store.write_jsonl(path, rows)
    idx = meta.setdefault("index", {})
    idx["danmaku"] = len(rows)
    idx["danmaku_at"] = store.now_iso()
    store.save_meta(video_id, meta)
    return {"video_id": meta["video_id"], "count": len(rows), "cached": False,
            "seconds": round(time.time() - t0, 2), "path": str(path)}


def get_danmaku(video_id: str, t0: float | None = None, t1: float | None = None,
                k: int = 20, cfg: dict | None = None) -> dict:
    """读取弹幕；给区间时返回该区间的均匀样本 + 密度。没有数据时提示先抓取。"""
    cfg = cfg or load_config()
    meta = store.load_meta(video_id)
    if not meta:
        raise KeyError(f"缓存中没有 {video_id}")
    rows = store.read_jsonl(store.vdir(video_id) / "danmaku.jsonl")
    if not rows:
        raise RuntimeError("还没有弹幕数据：先调用 danmaku(refresh=true) 或 index(danmaku=true)")
    t0 = 0.0 if t0 is None else max(0.0, float(t0))
    t1 = float(meta.get("duration_s") or rows[-1]["t"]) if t1 is None else float(t1)
    sub = [r for r in rows if t0 <= r["t"] <= t1]
    k = max(1, min(int(k), 200))
    step = max(1, len(sub) // k)
    picked = sub[::step][:k]
    span = max(1.0, t1 - t0)
    return {"video_id": meta["video_id"],
            "range": {"t0": round(t0, 2), "t1": round(t1, 2),
                      "label": f"{transcript.fmt_ts(t0)}-{transcript.fmt_ts(t1)}"},
            "count": len(sub), "total": len(rows),
            "density_per_min": round(len(sub) / span * 60, 1),
            "items": [{"t": r["t"], "text": r["text"]} for r in picked]}


def read(video_id: str, t0: float, t1: float, frames: int | None = None,
         cfg: dict | None = None, with_ocr: bool = False) -> dict:
    cfg = cfg or load_config()
    meta = store.load_meta(video_id)
    if not meta:
        raise KeyError(f"缓存中没有 {video_id}")
    store.touch(meta["video_id"])
    segments = _load_segments(video_id)
    if not segments:
        raise RuntimeError("还没有文本索引，请先 index")
    duration = float(meta.get("duration_s") or segments[-1]["t1"])
    t0 = max(0.0, float(t0))
    t1 = min(duration, float(t1))
    if t1 <= t0:
        raise ValueError(f"时间区间不合法: {t0} - {t1}")
    if frames is None:
        frames = int(cfg.get("read_frames_default", 4))
    frames = max(0, min(int(frames), int(cfg.get("read_frames_max", 6))))

    segs = transcript.segments_in_range(segments, t0, t1)
    scene_doc = store.read_json(store.shots_path(video_id)) or {}
    source = meta.get("video_cache_path") or meta["source"].get("path")
    frame_items: list[dict] = []
    if frames and source and Path(source).is_file():
        sb = [f for f in (scene_doc.get("storyboard") or []) if t0 <= f["t"] <= t1]
        if sb and len(sb) >= frames:
            step = len(sb) / frames
            times = [sb[min(len(sb) - 1, int(i * step + step / 2))]["t"] for i in range(frames)]
        else:
            # 故事板在该区间帧数不足：用区间均匀采样补齐，保证 read 总能拿到请求的帧数
            times = [f["t"] for f in sb]
            grid = [round(t0 + (t1 - t0) * (i + 0.5) / frames, 3) for i in range(frames)]
            for t in grid:
                if len(times) >= frames:
                    break
                if all(abs(t - x) >= 1.0 for x in times):
                    times.append(t)
            if len(times) < frames:   # 区间很小时强补，宁可挨得近也不缺帧
                for t in grid:
                    if len(times) >= frames:
                        break
                    if t not in times:
                        times.append(t)
            times = sorted(times)[:frames]
        try:
            frame_items = scenes.ensure_frames(source, video_id, times, cfg)
        except Exception as exc:  # 抽帧失败不阻断文本
            frame_items = [{"error": repr(exc)}]

    shots = [s for s in (scene_doc.get("shots") or []) if s["t1"] > t0 and s["t0"] < t1]
    truncated = False
    if len(segs) > 500:  # 区间过大时截断，提示模型缩小范围
        segs = segs[:500]
        truncated = True
    out = {
        "video_id": video_id,
        "title": meta.get("title"),
        "range": {"t0": round(t0, 3), "t1": round(t1, 3),
                  "label": f"{transcript.fmt_ts(t0)}-{transcript.fmt_ts(t1)}"},
        "segments": segs,
        "text": " ".join(s["text"] for s in segs),
        "frames": frame_items,
        "shots": shots[:40],
        "shot_count": len(shots),
        "truncated": truncated,
    }
    if with_ocr:
        out["ocr_note"] = "M0 未启用 OCR（主模型视觉读图即可；OCR 为 v2 可选）"
    return out


def _meta_query_hits(meta: dict, query: str) -> list[dict]:
    """标题/标签/简介命中（含拼音同音），返回“定位型”命中（放结果末尾，不挤占内容命中）。"""
    q = (query or "").strip()
    if not q:
        return []
    title = str(meta.get("title") or "")
    desc = str(meta.get("description") or "")
    tags = [str(t) for t in (meta.get("tags") or [])]
    ql = q.lower()
    where = ""
    if ql and ql in title.lower():
        where = "标题"
    elif any(ql and ql in t.lower() for t in tags):
        where = "标签"
    elif ql and ql in desc.lower():
        where = "简介"
    if not where:
        from . import pinyin
        if pinyin.AVAILABLE and pinyin.has_cjk(q):
            qp = pinyin.text_pinyin(q)
            if len(qp) >= 2:
                if qp in pinyin.text_pinyin(title):
                    where = "标题（同音）"
                elif any(qp in pinyin.text_pinyin(t) for t in tags):
                    where = "标签（同音）"
                elif qp in pinyin.text_pinyin(desc):
                    where = "简介（同音）"
    if not where:
        return []
    dur = float(meta.get("duration_s") or 20.0)
    return [{
        "score": 0.0,
        "t0": 0.0, "t1": round(min(20.0, dur), 2),
        "anchor": {"t0": 0.0, "t1": 0.0, "text": q, "mode": "metadata"},
        "text": f"[{where}命中] {title}" + (f"（标签：{'、'.join(tags[:6])}）" if tags else ""),
        "segment_indices": [],
        "match": "metadata",
        "where": where,
    }]


def search(video_id: str, query: str, k: int = 8, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    meta = store.load_meta(video_id)
    if not meta:
        raise KeyError(f"缓存中没有 {video_id}")
    store.touch(meta["video_id"])
    segments = _load_segments(video_id)
    hits = transcript.search_segments(segments, query, k=k)
    for h in hits:
        h.setdefault("match", "text")
    # 拼音同音兜底：升级普通命中的时间锚点（同音命中往往比 bigram 锚点更准）
    # 取比 k 更多的同音窗口，避免后面的同音命中因窗口配额被漏掉
    py_hits = transcript.pinyin_search(segments, query, k=max(k * 4, 16))
    py_by_seg: dict[int, list[dict]] = {}
    for ph in py_hits:
        for s in ph.get("segment_indices") or []:
            py_by_seg.setdefault(s, []).append(ph)
    for h in hits:
        best = None
        for s in h.get("segment_indices") or []:
            for ph in py_by_seg.get(s, []):
                a = ph.get("anchor") or {}
                cur = h.get("anchor") or {}
                if a.get("text") and len(a["text"]) > len(cur.get("text") or ""):
                    if best is None or len(a["text"]) > len(best.get("text") or ""):
                        best = a
        if best:
            h["anchor"] = best
            h["match"] = "pinyin"
            h["matched"] = best.get("text")
    covered: set[int] = set()
    for h in hits:
        covered.update(h.get("segment_indices") or [])
    for ph in py_hits:
        if not (set(ph.get("segment_indices") or []) & covered):
            hits.append(ph)
            covered.update(ph.get("segment_indices") or [])
    hits.sort(key=lambda h: h["t0"])
    hits = hits[:k]
    # 标题/标签/简介命中：作为额外的“定位型”命中附在内容命中之后（不计入 k 配额）
    meta_hits = _meta_query_hits(meta, query)
    if meta_hits:
        hits = hits + meta_hits[:1]
    scene_doc = store.read_json(store.shots_path(video_id)) or {}
    for h in hits:
        t_anchor = float((h.get("anchor") or {}).get("t0", h["t0"]))
        f = scenes.frame_for_time(scene_doc, t_anchor)
        if f:
            h["nearest_frame"] = {"t": f["t"], "path": f["path"]}
    return {"video_id": video_id, "title": meta.get("title"), "query": query,
            "hits": hits, "searched_segments": len(segments),
            "pinyin_fallback": any(h.get("match") == "pinyin" for h in hits)}


def get_transcript(video_id: str, t0: float | None = None, t1: float | None = None,
                   cfg: dict | None = None) -> dict:
    meta = store.load_meta(video_id)
    if not meta:
        raise KeyError(f"缓存中没有 {video_id}")
    store.touch(meta["video_id"])
    segments = _load_segments(video_id)
    if t0 is not None or t1 is not None:
        duration = float(meta.get("duration_s") or (segments[-1]["t1"] if segments else 0))
        segments = transcript.segments_in_range(segments, t0 or 0.0, t1 or duration)
    return {"video_id": video_id, "title": meta.get("title"),
            "segments": segments,
            "text": " ".join(s["text"] for s in segments)}


def rebuild_transcript(video_id: str, cfg: dict | None = None, language: str | None = None,
                       progress=None) -> dict:
    """只重建文本层：ASR（词级时间戳）-> 重分段 -> transcript.jsonl/srt。

    场景索引/故事板保持不动；已有视频缓存直接复用，音频临时抽取、用完按配置删除。
    """
    cfg = cfg or load_config()
    meta = store.load_meta(video_id)
    if not meta:
        raise KeyError(f"缓存中没有 {video_id}")
    kind = meta["source"]["kind"]
    video_path = meta.get("video_cache_path") or (meta["source"].get("path") if kind == "local" else None)
    t0 = time.time()
    if kind == "bilibili":
        wav = sources.ensure_bili_audio(video_id, meta["source"]["bvid"],
                                        int(meta["source"].get("page") or 1), cfg)
    else:
        if not video_path or not Path(video_path).is_file():
            raise FileNotFoundError(f"本地视频不存在: {video_path}")
        wav = sources.ensure_local_audio(video_id, video_path, cfg)
    audio_s = round(time.time() - t0, 2)

    from .asr import ASR
    asr = ASR(cfg=cfg, language=language)
    t0 = time.time()
    result = asr.transcribe(wav, language=language, progress=progress)
    asr_s = round(time.time() - t0, 2)
    raw = result.get("segments") or []
    reseg = transcript.resegment(
        raw,
        max_s=float(cfg.get("resegment_max_s", 12.0)),
        min_s=float(cfg.get("resegment_min_s", 0.8)),
        pause_s=float(cfg.get("resegment_pause_s", 0.6)))
    segments = reseg or raw
    if not segments:
        raise RuntimeError("ASR 未产出任何文本")
    rows = [dict(s, src="asr") for s in segments]
    store.write_jsonl(store.transcript_path(video_id), rows)
    transcript.write_srt(segments, str(store.vdir(video_id) / "transcript.srt"))
    if reseg:
        store.write_jsonl(store.vdir(video_id) / "transcript.raw.jsonl", raw)

    idx = meta.setdefault("index", {})
    idx.update({
        "transcript_source": "asr",
        "transcript_segments": len(rows),
        "asr_raw_segments": len(raw),
        "asr_words": result.get("word_count") or 0,
        "resegmented": bool(reseg),
        "asr_device": f"{result.get('device')}/{result.get('compute_type')}",
        "asr_language": result.get("language"),
        "asr_model": result.get("model"),
        "asr_rtf": round(float(result.get("rtf") or 0), 4),
    })
    tim = idx.setdefault("timings", {})
    tim["audio_extract_s"] = audio_s
    tim["asr_s"] = asr_s
    if not meta.get("duration_s"):
        meta["duration_s"] = result.get("duration_s")
    store.save_meta(video_id, meta)
    if not cfg.get("keep_audio"):
        for name in ("audio16k.wav", "audio.m4a"):
            p = store.source_dir(video_id) / name
            if p.is_file():
                try:
                    p.unlink()
                except OSError:
                    pass
    return {"video_id": video_id, "segments": len(rows), "raw_segments": len(raw),
            "words": result.get("word_count") or 0, "resegmented": bool(reseg),
            "language": result.get("language"), "audio_s": audio_s, "asr_s": asr_s,
            "rtf": result.get("rtf"),
            "max_seg_s": round(max((s["t1"] - s["t0"]) for s in segments), 2),
            "timings": tim}
