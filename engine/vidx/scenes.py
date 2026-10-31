# -*- coding: utf-8 -*-
"""场景切分 + 故事板关键帧（把镜头表变成可交给人/模型看的少量图片）。"""
from __future__ import annotations

import time
from pathlib import Path

from . import media, store
from .config import load_config


def build_scene_index(video_path: str, video_id: str, cfg: dict | None = None,
                      progress=None, force: bool = False,
                      codec: str | None = None) -> dict:
    cfg = cfg or load_config()
    out_path = store.shots_path(video_id)
    if not force:
        cached = store.read_json(out_path)
        if cached and cached.get("storyboard"):
            return cached

    def emit(stage: str, pct: float, msg: str = "") -> None:
        if progress:
            progress(stage, pct, msg)

    t_start = time.time()
    duration = media.duration_of(video_path)
    if not codec:
        try:
            probe = media.probe_media(video_path)
            codec = ((probe.get("video") or [{}])[0]).get("codec")
        except Exception:
            codec = None
    emit("scenes", 0.05, f"场景检测中（{duration / 60:.1f}min，阈值 {cfg['scene_threshold']}）")
    t0 = time.time()
    scene = media.scene_cuts(video_path, threshold=float(cfg["scene_threshold"]),
                             max_duration=duration, codec=codec)
    scene_s = round(time.time() - t0, 2)
    emit("scenes", 0.55, f"检测到 {len(scene['shots'])} 个镜头（{scene_s}s）")

    max_frames = int(cfg.get("storyboard_max", 60))
    picks = media.pick_storyboard(scene["shots"], duration, max_frames=max_frames)
    fdir = store.frames_dir(video_id)
    emit("frames", 0.6, f"抽取故事板 {len(picks)} 帧")
    t0 = time.time()
    frames = media.extract_frames(video_path, [p["t"] for p in picks], str(fdir),
                                  width=960, prefix="sb", tonemap=bool(cfg.get("hdr_tonemap", True)))
    for p, f in zip(picks, frames):
        f["shot_idx"] = p.get("shot_idx")
    frames_s = round(time.time() - t0, 2)

    doc = {
        "video_id": video_id,
        "duration_s": round(duration, 3),
        "threshold": scene["threshold"],
        "analysis": scene.get("analysis") or {"mode": "cpu"},
        "stats": scene["stats"],
        "shots": scene["shots"],
        "storyboard": frames,
        "timings": {"scene_s": scene_s, "frames_s": frames_s,
                    "total_s": round(time.time() - t_start, 2)},
        "built_at": store.now_iso(),
    }
    store.write_json(out_path, doc)
    emit("frames", 1.0, f"场景索引完成（{len(scene['shots'])} 镜头 / {len(frames)} 帧）")
    return doc


def frame_for_time(scene_doc: dict | None, t: float) -> dict | None:
    """找最接近某时间点的故事板帧。"""
    if not scene_doc:
        return None
    frames = scene_doc.get("storyboard") or []
    if not frames:
        return None
    return min(frames, key=lambda f: abs(f["t"] - t))


def shot_at(scene_doc: dict | None, t: float) -> dict | None:
    if not scene_doc:
        return None
    for s in scene_doc.get("shots") or []:
        if s["t0"] <= t <= s["t1"]:
            return s
    return None


def ensure_frames(video_path: str, video_id: str, times: list[float],
                  cfg: dict | None = None, width: int = 960) -> list[dict]:
    """按需抽帧（read 用）：落在 storyboard 已有的时间点直接复用文件。"""
    cfg = cfg or load_config()
    scene_doc = store.read_json(store.shots_path(video_id)) or {}
    existing = {round(f["t"], 1): f for f in scene_doc.get("storyboard") or []}
    out = []
    for t in times:
        hit = existing.get(round(t, 1))
        if hit and Path(hit["path"]).is_file():
            out.append({"t": hit["t"], "path": hit["path"], "reused": True})
            continue
        name = f"r{int(round(t * 1000)):08d}.png"
        p = store.frames_dir(video_id) / name
        media.extract_frame(video_path, t, str(p), width=width,
                            tonemap=bool(cfg.get("hdr_tonemap", True)))
        out.append({"t": round(t, 3), "path": str(p.resolve()), "reused": False})
    return out
