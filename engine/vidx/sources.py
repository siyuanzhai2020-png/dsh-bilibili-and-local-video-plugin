# -*- coding: utf-8 -*-
"""取源：bilibili（元数据/下载/字幕/弹幕）与本地文件（探测/内嵌字幕/侧车字幕）。"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Callable

from . import media, store, transcript
from .config import load_config

BILI_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
Progress = Callable[[str, float, str], None] | None

_SIDECAR_EXT = (".srt", ".ass", ".ssa", ".vtt", ".lrc")


# ---------------- bilibili HTTP ----------------

def _cfg() -> dict:
    return load_config()


def _headers(cfg: dict | None = None) -> dict:
    cfg = cfg or _cfg()
    return {
        "User-Agent": cfg["bilibili_uA"],
        "Referer": "https://www.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _http_json(url: str, params: dict | None = None, cfg: dict | None = None,
               retries: int = 3, timeout: int = 30) -> dict:
    cfg = cfg or _cfg()
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_headers(cfg))
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"bilibili 请求失败: {url} -> {last}")


def _resolve_short_url(url: str) -> str:
    if "b23.tv" not in url:
        return url
    try:
        req = urllib.request.Request(url, headers=_headers(), method="GET")
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.geturl()
    except Exception:
        return url


def parse_bili_input(source: str) -> dict:
    """从 URL/BV 文本提取 bvid 与分P号。"""
    s = _resolve_short_url(source.strip())
    m = BILI_RE.search(s)
    if not m:
        raise ValueError(f"不是 bilibili 视频链接/BV 号: {source}")
    page = 1
    try:
        q = urllib.parse.urlparse(s).query
        if q:
            p = urllib.parse.parse_qs(q).get("p") or urllib.parse.parse_qs(q).get("page")
            if p:
                page = max(1, int(p[0]))
    except Exception:
        pass
    return {"bvid": m.group(1), "page": page, "url": source.strip()}


def bili_view(bvid: str, cfg: dict | None = None) -> dict:
    cfg = cfg or _cfg()
    j = _http_json("https://api.bilibili.com/x/web-interface/view", {"bvid": bvid}, cfg)
    if j.get("code") != 0:
        raise RuntimeError(f"view API 失败 code={j.get('code')} msg={j.get('message')}")
    return j["data"]


def bili_tags(bvid: str, cfg: dict | None = None) -> list[str]:
    try:
        j = _http_json("https://api.bilibili.com/x/web-interface/view/detail",
                       {"bvid": bvid}, cfg)
        return [t.get("tag_name", "") for t in (j.get("data", {}).get("Tags") or []) if t.get("tag_name")]
    except Exception:
        return []


def bili_player(bvid: str, cid: int, cfg: dict | None = None) -> dict:
    """player API：字幕列表 + 章节 view_points（匿名通常为空）。"""
    base = "https://api.bilibili.com/x/player/wbi/v2"
    try:
        j = _http_json(base, {"bvid": bvid, "cid": cid}, cfg)
    except Exception:
        j = _http_json("https://api.bilibili.com/x/player/v2", {"bvid": bvid, "cid": cid}, cfg)
    if j.get("code") != 0:
        return {"subtitles": [], "view_points": [], "need_login_subtitle": None}
    d = j.get("data") or {}
    sub = d.get("subtitle") or {}
    return {
        "subtitles": sub.get("subtitles") or [],
        "need_login_subtitle": sub.get("need_login_subtitle"),
        "view_points": d.get("view_points") or [],
    }


def fetch_bili_subtitle_json(sub: dict, cfg: dict | None = None) -> list[dict]:
    """把字幕列表里的 subtitle_url 抓成 segments（登录态下才有内容）。"""
    cfg = cfg or _cfg()
    url = sub.get("subtitle_url") or ""
    if url.startswith("//"):
        url = "https:" + url
    if not url:
        return []
    try:
        req = urllib.request.Request(url, headers=_headers(cfg))
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        body = data.get("body") or []
        return [{"t0": round(float(b.get("from", 0)), 3),
                 "t1": round(float(b.get("to", 0)), 3),
                 "text": (b.get("content") or "").strip()} for b in body if b.get("content")]
    except Exception:
        return []


def fetch_danmaku(cid: int, cfg: dict | None = None, max_items: int | None = None) -> list[dict]:
    """弹幕 XML → [{t, mode, color, text}]（带播放时间戳，可用于“高能点/观众反应”）。

    注意：B 站接口返回 `Content-Encoding: deflate`，但是 **raw deflate**（无 zlib 头），
    必须用 `zlib.decompress(raw, -zlib.MAX_WBITS)`，否则会报 incorrect header check。
    """
    cfg = cfg or _cfg()
    max_items = int(max_items or cfg.get("danmaku_max", 20000))
    url = f"https://comment.bilibili.com/{cid}.xml"
    try:
        req = urllib.request.Request(url, headers=_headers(cfg))
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if "deflate" in enc:
                for wbits in (-zlib.MAX_WBITS, zlib.MAX_WBITS, 15 + 32):
                    try:
                        raw = zlib.decompress(raw, wbits)
                        break
                    except Exception:
                        continue
        root = ET.fromstring(raw)
        out = []
        for d in root.iter("d"):
            p = (d.get("p") or "").split(",")
            try:
                t = float(p[0])
            except Exception:
                continue
            text = (d.text or "").strip()
            if not text:
                continue
            try:
                mode = int(p[1]) if len(p) > 1 else 1
                color = int(p[3]) if len(p) > 3 else 16777215
            except Exception:
                mode, color = 1, 16777215
            out.append({"t": round(t, 2), "mode": mode, "color": color, "text": text})
            if len(out) >= max_items:
                break
        out.sort(key=lambda x: x["t"])
        return out
    except Exception:
        return []


# ---------------- yt-dlp 下载 ----------------

def _ytdlp(cfg: dict | None = None) -> str:
    cfg = cfg or _cfg()
    p = cfg.get("ytdlp")
    if p and Path(p).is_file():
        return p
    from shutil import which
    w = which("yt-dlp")
    if w:
        return w
    raise RuntimeError("找不到 yt-dlp，请设置 config.json 的 ytdlp 或 VIDX_YTDLP")


def _run_ytdlp(args: list[str], progress: Progress = None, stage: str = "download",
               timeout: int = 3600) -> None:
    cfg = _cfg()
    cmd = [_ytdlp(cfg)] + args + ["--ffmpeg-location", media.ffmpeg_path(),
                                  "--no-warnings", "--newline"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="ignore")
    t_start = time.time()
    tail: list[str] = []
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                tail = (tail + [line])[-6:]
            m = re.search(r"\[download\]\s+([\d.]+)%", line)
            if m and progress:
                pct = float(m.group(1)) / 100.0
                progress(stage, min(0.99, pct), line[:120])
            if time.time() - t_start > timeout:
                proc.kill()
                raise TimeoutError(f"yt-dlp 超时（>{timeout}s）")
    finally:
        code = proc.wait()
    if code != 0:
        raise RuntimeError("yt-dlp 失败: " + " | ".join(tail[-3:]))


def bili_info(bvid: str, page: int = 1, cfg: dict | None = None) -> dict:
    """yt-dlp -J 拿 formats/字幕列表（仅一次，含 duration）。

    分P 必须用 ``?p=N`` URL：``--playlist-items`` 与 ``--no-playlist`` 同时用时
    yt-dlp 会忽略分P选择，导致 p2 下载到 p1 内容（已实测踩坑）。
    """
    cfg = cfg or _cfg()
    url = f"https://www.bilibili.com/video/{bvid}?p={page}" if page > 1 \
        else f"https://www.bilibili.com/video/{bvid}"
    cmd = [_ytdlp(cfg), "-J", "--no-warnings", "--no-playlist", url]
    cp = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                        errors="ignore", timeout=180)
    if cp.returncode != 0:
        raise RuntimeError("yt-dlp -J 失败: " + (cp.stderr or "")[-300:])
    data = json.loads(cp.stdout)
    if data.get("_type") == "playlist":
        entries = data.get("entries") or []
        if entries:
            data = entries[0]
    return data


# ---------------- 下载到缓存 ----------------

def ensure_bili_video(video_id: str, bvid: str, page: int, cfg: dict | None = None,
                      progress: Progress = None) -> str:
    cfg = cfg or _cfg()
    sdir = store.source_dir(video_id)
    for cand in ("full.mp4", "full.mkv", "full.webm"):
        p = sdir / cand
        if p.is_file() and p.stat().st_size > 1024 * 1024:
            return str(p)
    height = int(cfg.get("download_height", 720))
    out = sdir / "full.%(ext)s"
    url = f"https://www.bilibili.com/video/{bvid}?p={page}" if page > 1 \
        else f"https://www.bilibili.com/video/{bvid}"
    args = ["-f", f"bv*[height<={height}]+ba/b[height<={height}]/b",
            "--merge-output-format", "mp4", "--no-playlist",
            "--write-info-json", "-o", str(out), url]
    _run_ytdlp(args, progress=progress, stage="download_video")
    for cand in ("full.mp4", "full.mkv", "full.webm"):
        p = sdir / cand
        if p.is_file():
            return str(p)
    raise RuntimeError("视频下载完成但找不到输出文件")


def ensure_bili_audio(video_id: str, bvid: str, page: int, cfg: dict | None = None,
                      progress: Progress = None) -> str:
    """下载 bilibili 音频 → 转 16k wav（有整片视频时直接抽轨）。"""
    cfg = cfg or _cfg()
    sdir = store.source_dir(video_id)
    wav = sdir / "audio16k.wav"
    if wav.is_file() and wav.stat().st_size > 1024:
        return str(wav)
    video = sdir / "full.mp4"
    if video.is_file():
        media.extract_audio(str(video), str(wav))
        return str(wav)
    m4a = sdir / "audio.m4a"
    if not (m4a.is_file() and m4a.stat().st_size > 1024):
        audio_format = cfg.get("audio_format", 30232)
        url = f"https://www.bilibili.com/video/{bvid}?p={page}" if page > 1 \
            else f"https://www.bilibili.com/video/{bvid}"
        args = ["-f", f"{audio_format}/bestaudio", "-x", "--audio-format", "m4a",
                "--no-playlist", "-o", str(sdir / "audio.%(ext)s"), url]
        _run_ytdlp(args, progress=progress, stage="download_audio")
    media.extract_audio(str(m4a), str(wav))
    return str(wav)


def ensure_local_audio(video_id: str, video_path: str, cfg: dict | None = None,
                       stream_index: int = 0) -> str:
    sdir = store.source_dir(video_id)
    wav = sdir / "audio16k.wav"
    if not (wav.is_file() and wav.stat().st_size > 1024):
        media.extract_audio(video_path, str(wav), stream_index=stream_index)
    return str(wav)


# ---------------- 字幕 ----------------

def sidecar_subtitles(video_path: str) -> list[dict]:
    p = Path(video_path)
    out = []
    for ext in _SIDECAR_EXT:
        cand = p.with_suffix(ext)
        if cand.is_file():
            out.append({"path": str(cand), "kind": "sidecar", "lang": ""})
    # 同名多语言：movie.zh.srt / movie.en.srt
    for f in p.parent.glob(p.stem + ".*"):
        if f.suffix.lower() in _SIDECAR_EXT and f.is_file():
            parts = f.name.split(".")
            lang = parts[-2] if len(parts) >= 3 else ""
            out.append({"path": str(f), "kind": "sidecar", "lang": lang})
    seen = set()
    uniq = []
    for s in out:
        if s["path"] in seen:
            continue
        seen.add(s["path"])
        uniq.append(s)
    return uniq


def embedded_subtitles(video_id: str, video_path: str, probe: dict | None = None,
                       cfg: dict | None = None, progress: Progress = None) -> list[dict]:
    cfg = cfg or _cfg()
    probe = probe or media.probe_media(video_path)
    sdir = store.source_dir(video_id)
    tracks = []
    for i, st in enumerate(probe.get("subtitle") or []):
        out = sdir / f"embedded_{i}_{st.get('lang') or 'und'}.srt"
        try:
            media.extract_subtitle(video_path, str(out), stream_index=i)
            segs = transcript.load_subtitle_file(str(out))
        except Exception:
            continue
        if segs:
            tracks.append({"path": str(out), "kind": "embedded", "lang": st.get("lang") or "",
                           "codec": st.get("codec"), "segments": segs})
    return tracks


def _pick_subtitle_track(tracks: list[dict], prefer: str | None = None) -> dict | None:
    if not tracks:
        return None
    order = [prefer] if prefer else ["zh", "zh-CN", "zh-Hans", "chi", "en", "eng", "fr", "fre"]

    def rank(t):
        lang = (t.get("lang") or "").lower()
        for i, want in enumerate(order):
            if want and want.lower() in lang:
                return i
        return len(order) + 1

    return sorted(tracks, key=lambda t: (rank(t), -len(t.get("segments") or [])))[0]


# ---------------- 统一 open ----------------

def _sidecar_info_json(p: Path) -> dict:
    """yt-dlp --write-info-json 产物的同名 sidecar：<stem>.info.json。"""
    for cand in (p.with_suffix(".info.json"),):
        if cand.is_file():
            try:
                import json as _json
                return _json.loads(cand.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                return {}
    return {}


def local_meta(path: str, cfg: dict | None = None) -> dict:
    """本地文件元数据；若 sidecar 带 bvid，则统一成 bili_<bvid>[_pN] 身份。"""
    cfg = cfg or _cfg()
    p = Path(path).expanduser().resolve()
    local_id = store.video_id_local(p)
    probe = media.probe_media(str(p))
    sidecars = sidecar_subtitles(str(p))
    info = _sidecar_info_json(p)
    raw_id = str(info.get("id") or "")
    m = re.match(r"^(BV[0-9A-Za-z]+?)(?:_p(\d+))?$", raw_id)
    if m:
        bvid, page = m.group(1), int(m.group(2) or 1)
        video_id = store.video_id_bili(bvid, page)
        if video_id != local_id:
            store.add_aliases({local_id: video_id})
    else:
        bvid, page = "", 1
        video_id = local_id
    existing = store.load_meta(video_id) or {}
    checks = []
    for c in info.get("chapters") or []:
        try:
            checks.append({"t0": round(float(c.get("start_time", 0)), 2),
                           "t1": round(float(c.get("end_time", 0)), 2),
                           "title": (c.get("title") or "").strip()})
        except Exception:
            continue
    old_src = existing.get("source") or {}
    local_paths = sorted({*(old_src.get("local_paths") or []), str(p)})
    source = {"kind": "local", "path": str(p), "local_paths": local_paths}
    if bvid:
        source.update({"bvid": bvid,
                       "webpage_url": info.get("webpage_url")
                       or f"https://www.bilibili.com/video/{bvid}"
                       + (f"?p={page}" if page > 1 else "")})
        if page > 1:
            source["page"] = page
    meta = {
        "video_id": video_id,
        "source": source,
        "title": existing.get("title") or (info.get("title") or p.stem).strip(),
        "series_title": existing.get("series_title") or "",
        "duration_s": float(probe.get("duration_s") or info.get("duration")
                            or existing.get("duration_s") or 0.0),
        "description": existing.get("description") or info.get("description") or "",
        "tags": [str(t) for t in (info.get("tags") or existing.get("tags") or [])],
        "owner": existing.get("owner") or info.get("uploader") or "",
        "media": probe,
        "sidecar_subtitles": sidecars,
        "platform_chapters": (existing.get("platform_chapters")
                              or checks or [{"t0": c["t0"], "t1": c["t1"],
                                             "title": c["title"]}
                                            for c in probe.get("chapters") or []]),
        "info_json": str(p.with_suffix(".info.json")) if info else "",
        "created_at": existing.get("created_at") or store.now_iso(),
        "aliases": sorted(set((existing.get("aliases") or []) +
                              ([local_id] if local_id != video_id else []))),
    }
    # 已有 API 元数据（pages/subtitle_tracks 等）保留
    for k in ("pages", "subtitle_tracks", "need_login_subtitle"):
        if existing.get(k):
            meta[k] = existing[k]
    meta["index"] = existing.get("index") or {"status": "none"}
    return meta


def bili_meta(source: str, cfg: dict | None = None) -> dict:
    cfg = cfg or _cfg()
    parsed = parse_bili_input(source)
    bvid, page = parsed["bvid"], parsed["page"]
    view = bili_view(bvid, cfg)
    pages = view.get("pages") or []
    if page > len(pages) and pages:
        page = 1
    pg = (pages[page - 1] if pages else {}) or {}
    cid = pg.get("cid") or view.get("cid")
    video_id = store.video_id_bili(bvid, page)
    existing = store.load_meta(video_id) or {}
    player = bili_player(bvid, cid, cfg) if cid else {"subtitles": [], "view_points": [], "need_login_subtitle": None}
    tags = bili_tags(bvid, cfg)
    view_points = player.get("view_points") or []
    chapters = []
    for i, vp in enumerate(view_points):
        chapters.append({
            "t0": round(float(vp.get("from", 0)), 2),
            "t1": round(float(vp.get("to", vp.get("from", 0)) + 1), 2),
            "title": (vp.get("content") or vp.get("title") or f"chapter {i + 1}").strip(),
        })
    meta = {
        "video_id": video_id,
        "source": {"kind": "bilibili", "url": parsed["url"], "bvid": bvid,
                   "page": page, "cid": cid},
        "title": ((pg.get("part") if page > 1 and pg.get("part") else view.get("title")) or "").strip(),
        "series_title": view.get("title") or "",
        "duration_s": float(pg.get("duration") or view.get("duration") or 0),
        "description": view.get("desc") or "",
        "tags": tags,
        "owner": (view.get("owner") or {}).get("name") or "",
        "pages": [{"page": p.get("page"), "title": p.get("part"), "duration_s": p.get("duration"),
                   "cid": p.get("cid")} for p in pages],
        "platform_chapters": chapters,
        "subtitle_tracks": [{"lan": s.get("lan"), "lan_doc": s.get("lan_doc"),
                             "subtitle_url": s.get("subtitle_url")}
                            for s in player.get("subtitles") or []],
        "need_login_subtitle": player.get("need_login_subtitle"),
        "created_at": existing.get("created_at") or store.now_iso(),
    }
    meta["index"] = existing.get("index") or {"status": "none"}
    old_src = existing.get("source") or {}
    if old_src.get("local_paths"):
        meta["source"]["local_paths"] = old_src["local_paths"]
    if existing.get("aliases"):
        meta["aliases"] = existing["aliases"]
    if existing.get("video_cache_path"):
        meta["video_cache_path"] = existing["video_cache_path"]
    if existing.get("last_used"):
        meta["last_used"] = existing["last_used"]
    return meta


def open_source(source: str, cfg: dict | None = None) -> dict:
    """统一 open：本地文件或 bilibili URL/BV。返回并保存 meta。"""
    cfg = cfg or _cfg()
    src = source.strip().strip('"').strip("'")
    if BILI_RE.search(src) or "bilibili.com" in src or "b23.tv" in src:
        meta = bili_meta(src, cfg)
    else:
        p = Path(src).expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"找不到本地文件: {src}")
        meta = local_meta(str(p), cfg)
    store.save_meta(meta["video_id"], meta)
    return meta
