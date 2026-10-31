# -*- coding: utf-8 -*-
"""ffmpeg 封装：媒体探测、抽音轨、抽字幕、抽帧、场景切分。

本机 ffmpeg（_work/bin/ffmpeg.exe）没有附带 ffprobe，所以探测统一走
`ffmpeg -hide_banner -i <file>` 的 stderr 解析（容器/流/章节都够用）。
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .config import load_config

_DUR = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_STREAM = re.compile(
    r"Stream\s+#0:(\d+)(?:\[[^\]]*\])?(?:\(([^)]*)\))?:\s*(Video|Audio|Subtitle|Data|Attachment):\s*([^\n]*)")
_CHAPTER = re.compile(r"Chapter\s+#0:(\d+):\s*start\s+([0-9.]+),\s*end\s+([0-9.]+)")
_CHAPTER_TITLE = re.compile(r"title\s*:\s*(.+)")
_RES = re.compile(r"(\d{2,5})x(\d{2,5})")
_FPS = re.compile(r"([\d.]+)\s*fps")
_HZ = re.compile(r"(\d+)\s*Hz")
_CH = re.compile(r"\b(mono|stereo|quad|hexadecagonal|octagonal)\b|(\d+)\s+channels")


class MediaError(RuntimeError):
    pass


def ffmpeg_path() -> str:
    p = load_config()["ffmpeg"]
    if p and Path(p).is_file():
        return p
    from shutil import which
    w = which("ffmpeg")
    if w:
        return w
    raise MediaError("找不到 ffmpeg，请设置 VIDX_FFMPEG 或 config.json 的 ffmpeg")


def _run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="ignore", timeout=timeout)


def _log_error(cp: subprocess.CompletedProcess, what: str) -> None:
    tail = ((cp.stderr or "") + "\n" + (cp.stdout or "")).strip().splitlines()[-8:]
    raise MediaError(f"{what} 失败 (exit={cp.returncode}): " + " | ".join(tail))


def duration_of(path: str) -> float:
    cp = _run([ffmpeg_path(), "-hide_banner", "-i", str(path)], timeout=120)
    m = _DUR.search(cp.stderr or "")
    if not m:
        raise MediaError(f"无法识别媒体时长: {path}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def probe_media(path: str) -> dict:
    """解析 ffmpeg -i，返回容器/视频/音频/字幕流与章节。"""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"媒体文件不存在: {p}")
    cp = _run([ffmpeg_path(), "-hide_banner", "-i", str(p)], timeout=180)
    text = cp.stderr or ""
    info: dict = {
        "path": str(p.resolve()), "size_bytes": p.stat().st_size,
        "duration_s": None, "format": None,
        "video": [], "audio": [], "subtitle": [], "chapters": [],
        "hdr": False,
    }
    m = _DUR.search(text)
    if m:
        info["duration_s"] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 3)
    m = re.search(r"Input #0,\s*([^\n]+)", text)
    if m:
        info["format"] = m.group(1).strip()

    for line in text.splitlines():
        s = _STREAM.search(line)
        if not s:
            continue
        idx, lang, kind, rest = int(s.group(1)), s.group(2), s.group(3), s.group(4).strip()
        if kind == "Video":
            codec = re.split(r"[,\s]", rest, maxsplit=1)[0]
            res = _RES.search(rest)
            fps = _FPS.search(rest)
            info["video"].append({
                "index": idx, "codec": codec, "lang": lang,
                "width": int(res.group(1)) if res else None,
                "height": int(res.group(2)) if res else None,
                "fps": float(fps.group(1)) if fps else None,
                "hdr": ("smpte2084" in rest or "arib-std-b67" in rest or "bt2020" in rest),
            })
            if "smpte2084" in rest or "arib-std-b67" in rest or "bt2020" in rest:
                info["hdr"] = True
        elif kind == "Audio":
            codec = re.split(r"[,\s]", rest, maxsplit=1)[0]
            hz = _HZ.search(rest)
            ch = _CH.search(rest)
            info["audio"].append({
                "index": idx, "codec": codec, "lang": lang,
                "sample_rate": int(hz.group(1)) if hz else None,
                "channels": (ch.group(1) or (ch.group(2) + "ch")) if ch else None,
            })
        elif kind == "Subtitle":
            codec = re.split(r"[,\s]", rest, maxsplit=1)[0]
            info["subtitle"].append({"index": idx, "codec": codec, "lang": lang})

    # 章节
    lines = text.splitlines()
    for i, line in enumerate(lines):
        c = _CHAPTER.search(line)
        if not c:
            continue
        title = ""
        for j in range(i + 1, min(i + 4, len(lines))):
            t = _CHAPTER_TITLE.search(lines[j])
            if t:
                title = t.group(1).strip()
                break
        info["chapters"].append({"t0": round(float(c.group(2)), 3),
                                 "t1": round(float(c.group(3)), 3),
                                 "title": title or f"chapter {c.group(1)}"})
    info["chapters"].sort(key=lambda x: x["t0"])
    return info


def _tonemap_filter() -> str:
    return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
            "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def extract_audio(video_path: str, out_wav: str, stream_index: int = 0,
                  start: float | None = None, duration: float | None = None) -> str:
    """抽 16kHz 单声道 PCM wav（ASR 用）。"""
    out = Path(out_wav)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(video_path), "-map", f"0:a:{stream_index}", "-vn",
            "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += [str(out)]
    cp = _run(cmd, timeout=1800)
    if cp.returncode != 0:
        _log_error(cp, "抽取音频")
    return str(out)


def extract_subtitle(video_path: str, out_path: str, stream_index: int = 0) -> str:
    """把内嵌字幕轨转成 srt（ass/subrip/mov_text 均可）。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path),
           "-map", f"0:s:{stream_index}", "-c:s", "srt", str(out)]
    cp = _run(cmd, timeout=600)
    if cp.returncode != 0 or not out.is_file():
        _log_error(cp, "抽取内嵌字幕")
    return str(out)


def _frame_filter(width: int, tonemap: bool = False) -> str:
    parts = []
    if tonemap:
        parts.append(_tonemap_filter())
    parts.append(f"scale={width}:-2")
    return ",".join(parts)


def extract_frame(video_path: str, t: float, out_png: str, width: int = 960,
                  tonemap: bool = False) -> str:
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{max(0.0, t):.3f}", "-i", str(video_path),
           "-frames:v", "1", "-vf", _frame_filter(width, tonemap), str(out)]
    cp = _run(cmd, timeout=120)
    if cp.returncode != 0 or not out.is_file():
        _log_error(cp, f"抽帧 t={t:.1f}s")
    return str(out)


def extract_frames(video_path: str, times: list[float], out_dir: str,
                   width: int = 960, prefix: str = "t", tonemap: bool = False) -> list[dict]:
    out: list[dict] = []
    od = Path(out_dir)
    od.mkdir(parents=True, exist_ok=True)
    for t in times:
        name = f"{prefix}{int(round(t * 1000)):08d}.png"
        p = od / name
        extract_frame(video_path, t, str(p), width=width, tonemap=tonemap)
        out.append({"t": round(t, 3), "path": str(p.resolve())})
    return out


# 常见编码 -> CUVID 硬解 decoder（GPU 解码后再做 CPU scene 打分；失败自动回退软解）
_CUVID = {"h264": "h264_cuvid", "avc": "h264_cuvid",
          "hevc": "hevc_cuvid", "h265": "hevc_cuvid",
          "av1": "av1_cuvid", "vp9": "vp9_cuvid",
          "mpeg2video": "mpeg2_cuvid", "vc1": "vc1_cuvid"}

_PTS = re.compile(r"pts_time:([0-9.]+)")


def _scene_scan_range(video_path: str, thr: float, start: float, end: float,
                      decoder: str | None = None, timeout: int = 1800) -> list[float]:
    """扫描 [start,end) 的切点（输入侧 seek，pts_time 相对 start）。失败抛 MediaError。"""
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "info"]
    if decoder:
        cmd += ["-c:v", decoder]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-t", f"{max(0.1, end - start):.3f}", "-i", str(video_path),
            "-filter:v", f"select='gt(scene,{thr})',showinfo",
            "-an", "-f", "null", "-"]
    cp = _run(cmd, timeout=timeout)
    if cp.returncode != 0:
        tail = ((cp.stderr or "") + "\n" + (cp.stdout or "")).strip().splitlines()[-3:]
        raise MediaError(f"scene scan {start:.0f}-{end:.0f}s 失败 (exit={cp.returncode}): "
                         + " | ".join(tail))
    return sorted({round(start + float(m.group(1)), 3)
                   for m in _PTS.finditer(cp.stderr or "")})


def _scene_scan_chunk(video_path: str, thr: float, start: float, end: float,
                      decoder: str | None, depth: int = 0,
                      fallbacks: list | None = None) -> list[float]:
    """硬解分块扫描；崩溃/不支持时对半拆分，再不行回退软解。"""
    if fallbacks is None:
        fallbacks = []
    try:
        return _scene_scan_range(video_path, thr, start, end, decoder=decoder)
    except MediaError:
        span = end - start
        if decoder and span > 75 and depth < 2:
            mid = round(start + span / 2, 3)
            return (_scene_scan_chunk(video_path, thr, start, mid, decoder, depth + 1, fallbacks) +
                    _scene_scan_chunk(video_path, thr, mid, end, decoder, depth + 1, fallbacks))
        fallbacks.append(round(start, 1))
        return _scene_scan_range(video_path, thr, start, end, decoder=None)


def scene_cuts(video_path: str, threshold: float = 0.30,
               max_duration: float | None = None, timeout: int = 3600,
               codec: str | None = None, hw: bool | None = None,
               chunk_s: int | None = None) -> dict:
    """ffmpeg scene 检测：返回 {"total":..., "cuts":[...], "shots":[...], "stats":{...}}。

    hw=True 时用 CUVID 硬解 + 固定时长分块（避免长进程/硬解偶发崩溃），
    失败块自动拆分并回退软解；切点仍是全分辨率 scene 打分，精度与软解一致。
    """
    thr = float(threshold)
    cfg = load_config()
    hw = bool(cfg.get("scene_hw", True)) if hw is None else bool(hw)
    chunk_s = int(cfg.get("scene_chunk_s", 300)) if chunk_s is None else int(chunk_s)
    total = float(max_duration or duration_of(video_path))
    hw_codecs = {str(c).lower() for c in (cfg.get("scene_hw_codecs") or ["av1"])}
    decoder = _CUVID.get((codec or "").lower()) if (hw and (codec or "").lower() in hw_codecs) else None
    analysis: dict = {"mode": "cpu", "codec": codec, "chunk_s": None,
                      "chunks": 1, "fallback_chunks": []}
    cuts: list[float] = []
    if decoder:
        from concurrent.futures import ThreadPoolExecutor
        starts = []
        pos = 0.0
        while pos < total - 0.05:
            starts.append(pos)
            pos += chunk_s
        ranges = [(s, min(total, s + chunk_s + 0.5)) for s in starts]  # 0.5s 重叠
        fallbacks: list[float] = []
        workers = max(1, min(int(cfg.get("scene_workers", 3)), len(ranges)))
        try:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(
                    lambda r: _scene_scan_chunk(video_path, thr, r[0], r[1], decoder,
                                                fallbacks=fallbacks), ranges))
            for part in results:
                cuts += part
            cuts.sort()
            dedup: list[float] = []
            for c in cuts:
                if dedup and c - dedup[-1] < 0.25:
                    continue
                dedup.append(c)
            cuts = dedup
            analysis = {"mode": "hw", "decoder": decoder, "codec": codec,
                        "chunk_s": chunk_s, "chunks": len(ranges), "workers": workers,
                        "fallback_chunks": fallbacks}
        except Exception as exc:  # 硬解/分块整体异常：回退整片软解
            cuts = []
            analysis = {"mode": "cpu", "codec": codec, "hw_error": repr(exc)[:200]}
            decoder = None
    if not decoder and not cuts:
        cuts = _scene_scan_range(video_path, thr, 0.0, total, decoder=None)

    bounds = [0.0] + [c for c in cuts if 0.0 < c < total] + [round(total, 3)]
    shots = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        if b - a < 0.04:
            continue
        shots.append({"idx": len(shots) + 1, "t0": round(a, 3), "t1": round(b, 3),
                      "dur": round(b - a, 3)})
    durs = sorted(s["dur"] for s in shots) or [0.0]
    n = len(durs)
    stats = {
        "shots": n,
        "span_min": round(total / 60, 2),
        "asl_mean_s": round(sum(durs) / n, 2) if n else 0,
        "asl_median_s": round(durs[n // 2], 2),
        "p90_s": round(durs[int(n * 0.9)], 2),
        "under_2s": sum(1 for d in durs if d < 2),
        "over_20s": sum(1 for d in durs if d > 20),
        "longest": durs[-1],
    }
    return {"threshold": thr, "total": round(total, 3), "stats": stats, "shots": shots,
            "analysis": analysis}


def pick_storyboard(shots: list[dict], total: float, max_frames: int = 60) -> list[dict]:
    """从镜头表挑代表帧：均匀覆盖 + 镜头中点；找不到镜头时退回均匀采样。"""
    if max_frames <= 0:
        return []
    if not shots:
        step = max(2.0, total / max_frames)
        times = [min(total - 0.5, 1.0 + i * step) for i in range(max_frames)]
        return [{"t": round(t, 3), "shot_idx": None} for t in times]
    n = len(shots)
    if n <= max_frames:
        idxs = list(range(n))
    else:
        # 先均匀取一半，再补最长镜头
        k = max_frames
        step = n / k
        idxs = sorted({min(n - 1, int(i * step + step / 2)) for i in range(k)})
        if len(idxs) < k:
            longest = sorted(range(n), key=lambda i: shots[i]["dur"], reverse=True)
            for i in longest:
                if i not in idxs:
                    idxs.append(i)
                if len(idxs) >= k:
                    break
            idxs = sorted(idxs)[:k]
    out = []
    for i in idxs:
        s = shots[i]
        t = round((s["t0"] + s["t1"]) / 2, 3)
        if t >= total:
            t = max(0.0, total - 0.5)
        out.append({"t": t, "shot_idx": s.get("idx")})
    # 长镜头/静态画面视频（镜头数远少于目标帧数）额外均匀补帧，避免整段只有 1 张
    if total > 0 and len(out) < max_frames // 3:
        step = total / max_frames
        for i in range(max_frames):
            t = round(min(total - 0.2, (i + 0.5) * step), 3)
            if all(abs(t - x["t"]) > max(2.0, step * 0.5) for x in out):
                out.append({"t": t, "shot_idx": None})
    out.sort(key=lambda x: x["t"])
    return out[:max_frames]
