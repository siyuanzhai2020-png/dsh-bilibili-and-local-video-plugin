# -*- coding: utf-8 -*-
"""缓存目录、video_id 与 JSON 持久化。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Iterable

from .config import cache_dir

_ALIAS_FILE = "aliases.json"
_ALIAS_STATE: dict = {"mtime": None, "map": {}}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------------- 身份归一：bvid 为主，别名表向后兼容 ----------------

def aliases_path() -> Path:
    return cache_dir() / _ALIAS_FILE


def load_aliases(force: bool = False) -> dict:
    p = aliases_path()
    try:
        mt = p.stat().st_mtime_ns
    except OSError:
        return {}
    if not force and _ALIAS_STATE["mtime"] == mt:
        return _ALIAS_STATE["map"]
    m = read_json(p, {}) or {}
    if not isinstance(m, dict):
        m = {}
    _ALIAS_STATE.update({"mtime": mt, "map": m})
    return m


def save_aliases(mapping: dict) -> None:
    write_json(aliases_path(), dict(sorted(mapping.items())))
    _ALIAS_STATE.update({"mtime": aliases_path().stat().st_mtime_ns, "map": dict(mapping)})


def add_aliases(pairs: dict) -> dict:
    """把 alias -> canonical 写进别名表（幂等，自动去重/防自环）。"""
    m = dict(load_aliases(force=True))
    for a, c in (pairs or {}).items():
        if a and c and a != c:
            m[str(a)] = str(c)
    save_aliases(m)
    return m


def resolve_id(video_id: str) -> str:
    """把任意 id（旧 local_* / 别名）解析成 canonical id。"""
    if not video_id:
        return video_id
    m = load_aliases()
    cur, seen = str(video_id), set()
    while cur in m and cur not in seen:
        seen.add(cur)
        cur = str(m[cur])
    return cur


def vdir(video_id: str) -> Path:
    d = cache_dir() / sanitize(resolve_id(video_id), 120)
    d.mkdir(parents=True, exist_ok=True)
    return d


def raw_vdir(video_id: str) -> Path:
    """不做别名解析的目录（迁移/清理时用）。"""
    return cache_dir() / sanitize(str(video_id), 120)


def meta_path(video_id: str) -> Path:
    return vdir(video_id) / "meta.json"


def sanitize(name: str, maxlen: int = 80) -> str:
    name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", name, flags=re.UNICODE)
    return name[:maxlen].strip("._") or "video"


def _file_signature(path: Path, chunk: int = 1024 * 1024) -> str:
    """大小 + 首尾 1MB 的 sha1：大文件不必全量 hash，改名/移动仍可识别。"""
    h = hashlib.sha1()
    size = path.stat().st_size
    h.update(str(size).encode())
    with path.open("rb") as f:
        h.update(f.read(chunk))
        if size > chunk * 2:
            f.seek(-chunk, os.SEEK_END)
            h.update(f.read(chunk))
    return h.hexdigest()


def video_id_local(path: str | os.PathLike) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"本地视频不存在: {p}")
    return "local_" + _file_signature(p)[:16]


def video_id_bili(bvid: str, page: int | None = None) -> str:
    vid = f"bili_{bvid}"
    if page and page > 1:
        vid += f"_p{page}"
    return vid


def transcript_path(video_id: str) -> Path:
    return vdir(video_id) / "transcript.jsonl"


def shots_path(video_id: str) -> Path:
    return vdir(video_id) / "shots.json"


def frames_dir(video_id: str) -> Path:
    d = vdir(video_id) / "frames"
    d.mkdir(parents=True, exist_ok=True)
    return d


def source_dir(video_id: str) -> Path:
    d = vdir(video_id) / "source"
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_json(path: str | os.PathLike, default: Any = None) -> Any:
    p = Path(path)
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: str | os.PathLike, obj: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def write_jsonl(path: str | os.PathLike, rows: Iterable[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, p)


def read_jsonl(path: str | os.PathLike) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    return rows


def load_meta(video_id: str) -> dict | None:
    return read_json(meta_path(video_id))


def save_meta(video_id: str, meta: dict) -> None:
    meta["updated_at"] = now_iso()
    write_json(meta_path(video_id), meta)


def touch(video_id: str) -> None:
    """记录最近使用时间（LRU 依据）；失败不影响主流程。"""
    try:
        vid = resolve_id(video_id)
        meta = load_meta(vid)
        if not meta:
            return
        meta["last_used"] = now_iso()
        save_meta(vid, meta)
    except Exception:
        pass


def _dir_size(d: Path) -> int:
    try:
        return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
    except Exception:
        return 0


def _video_entries() -> list[dict]:
    root = cache_dir()
    out = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        meta = read_json(d / "meta.json", {}) or {}
        out.append({"video_id": d.name, "dir": d, "meta": meta,
                    "size": _dir_size(d)})
    return out


def cache_summary(include_trash: bool = False) -> dict:
    root = cache_dir()
    entries = _video_entries()
    total = sum(e["size"] for e in entries)
    trash = root / ".trash"
    trash_size = _dir_size(trash) if trash.is_dir() else 0
    aliases = load_aliases()
    items = [{
        "video_id": e["video_id"],
        "mb": round(e["size"] / 1024 / 1024, 1),
        "title": (e["meta"].get("title") or "")[:60],
        "status": (e["meta"].get("index") or {}).get("status"),
        "last_used": e["meta"].get("last_used") or "",
        "pinned": bool(e["meta"].get("pinned")),
        "aliases": [a for a, c in aliases.items() if c == e["video_id"]],
    } for e in entries]
    out = {"root": str(root), "total_mb": round(total / 1024 / 1024, 1),
           "count": len(items), "items": items,
           "trash_mb": round(trash_size / 1024 / 1024, 1),
           "alias_count": len(aliases)}
    if include_trash:
        out["trash_dir"] = str(trash)
    return out


def cache_prune(cap_gb: float = 10.0, dry_run: bool = True,
                keep_pinned: bool = True) -> dict:
    """按 last_used 从旧到新淘汰整视频目录，直到总量 <= cap_gb。

    - 只删缓存目录（不碰用户原始文件），默认 dry_run 只给清单；
    - `.trash/` 里迁移备份视为最旧，先整个清掉。
    """
    root = cache_dir()
    cap_bytes = int(float(cap_gb) * 1024 ** 3)
    entries = _video_entries()
    total = sum(e["size"] for e in entries)
    trash = root / ".trash"
    trash_size = _dir_size(trash) if trash.is_dir() else 0
    pool = sorted(entries, key=lambda e: (e["meta"].get("last_used") or "0000"))
    victims, cur = [], total + trash_size
    if cur > cap_bytes and trash_size:
        victims.append({"video_id": ".trash", "dir": trash, "size": trash_size,
                        "last_used": "0000", "pinned": False, "kind": "trash"})
        cur -= trash_size
    for e in pool:
        if cur <= cap_bytes:
            break
        pinned = bool(e["meta"].get("pinned"))
        if pinned and keep_pinned:
            continue
        victims.append({"video_id": e["video_id"], "dir": e["dir"], "size": e["size"],
                        "last_used": e["meta"].get("last_used") or "",
                        "pinned": pinned, "kind": "video"})
        cur -= e["size"]
    if not dry_run:
        for v in victims:
            shutil.rmtree(v["dir"], ignore_errors=True)
    return {
        "cap_gb": float(cap_gb), "dry_run": bool(dry_run),
        "total_mb": round((total + trash_size) / 1024 / 1024, 1),
        "trash_mb": round(trash_size / 1024 / 1024, 1),
        "after_mb": round(max(cur, 0) / 1024 / 1024, 1),
        "victims": [{"video_id": v["video_id"],
                     "mb": round(v["size"] / 1024 / 1024, 1),
                     "last_used": v["last_used"], "pinned": v["pinned"],
                     "kind": v["kind"]} for v in victims],
        "deleted": [] if dry_run else [v["video_id"] for v in victims],
    }


# ---------------- 旧 local_* -> bili_* 身份迁移 ----------------

def _canonical_of(meta: dict) -> str:
    src = meta.get("source") or {}
    bvid = str(src.get("bvid") or "")
    m = re.match(r"^(BV[0-9A-Za-z]+?)(?:_p(\d+))?$", bvid)
    if m:
        return video_id_bili(m.group(1), int(m.group(2) or src.get("page") or 1))
    return str(meta.get("video_id") or "")


def _mig_score(meta: dict) -> tuple:
    idx = meta.get("index") or {}
    return (bool(idx.get("asr_words")), idx.get("status") == "ready",
            idx.get("transcript_source") == "asr", int(idx.get("frames") or 0),
            int(idx.get("transcript_segments") or 0))


def _merge_meta(existing: dict, primary: dict, canonical: str, aliases: list[str]) -> dict:
    """以 API 元数据（existing）为底，合入最佳索引（primary）。"""
    meta = dict(existing or primary)
    for k in ("index", "media", "video_cache_path", "sidecar_subtitles", "duration_s",
              "title", "series_title", "owner", "tags", "description",
              "platform_chapters", "pages", "transcript_tracks"):
        if primary.get(k):
            meta[k] = primary[k]
    base_src = dict((existing or {}).get("source") or {})
    prim_src = dict(primary.get("source") or {})
    src = {**prim_src, **base_src} if base_src.get("kind") == "bilibili" else prim_src
    paths = set(src.get("local_paths") or [])
    for s in ((existing or {}).get("source") or {}, prim_src):
        if s.get("kind") == "local" and s.get("path"):
            paths.add(s["path"])
        paths.update(s.get("local_paths") or [])
    if paths:
        src["local_paths"] = sorted(paths)
    meta["source"] = src
    meta["video_id"] = canonical
    meta["aliases"] = sorted(set(aliases))
    return meta


def migrate_aliases(dry_run: bool = True) -> dict:
    """把同一视频的 local_* / bili_* 多条缓存合并到 canonical（bili_<bvid>）。

    默认 dry_run 只出方案；apply 时：备份旧 canonical 目录 -> 复制最佳索引 ->
    重写 shots.json 里的绝对路径 -> 写别名表 -> 其余目录移入 .trash。
    """
    root = cache_dir()
    entries = []
    for e in _video_entries():
        canon = _canonical_of(e["meta"])
        if not canon:
            continue
        entries.append({**e, "canonical": canon, "score": _mig_score(e["meta"])})
    groups: dict[str, list[dict]] = {}
    for e in entries:
        groups.setdefault(e["canonical"], []).append(e)
    plan = []
    for canon, items in groups.items():
        if len(items) <= 1 and items[0]["video_id"] == canon:
            continue
        primary = max(items, key=lambda x: x["score"])
        plan.append({
            "canonical": canon,
            "primary": primary["video_id"],
            "primary_dir": str(primary["dir"]),
            "aliases": sorted(i["video_id"] for i in items if i["video_id"] != canon),
            "members": [{"video_id": i["video_id"], "mb": round(i["size"] / 1024 / 1024, 1),
                         "has_words": bool((i["meta"].get("index") or {}).get("asr_words"))}
                        for i in items],
        })
    result = {"dry_run": bool(dry_run), "groups": len(plan), "plan": plan,
              "trash_dir": str(root / ".trash")}
    if dry_run or not plan:
        return result
    ts = time.strftime("%Y%m%d-%H%M%S")
    trash = root / ".trash" / ts
    for g in plan:
        canon = g["canonical"]
        canon_dir = raw_vdir(canon)
        prim_dir = Path(g["primary_dir"])
        existing = read_json(canon_dir / "meta.json", {}) if canon_dir.is_dir() else {}
        # 1) 备份已有 canonical 目录
        if canon_dir.is_dir() and any(canon_dir.iterdir()):
            trash.mkdir(parents=True, exist_ok=True)
            shutil.move(str(canon_dir), str(trash / canon_dir.name))
        canon_dir.mkdir(parents=True, exist_ok=True)
        # 2) 复制最佳索引文件（meta.json 最后单独合并写）
        for item in list(prim_dir.iterdir()):
            if item.name == "meta.json":
                continue
            dst = canon_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)
        # 3) 重写 shots.json 里的绝对路径（frames 等）
        shots_file = canon_dir / "shots.json"
        if shots_file.is_file():
            doc = read_json(shots_file, {}) or {}
            old, new = str(prim_dir), str(canon_dir)

            def fix(v):
                return v.replace(old, new) if isinstance(v, str) else v
            for f in doc.get("storyboard") or []:
                f["path"] = fix(f.get("path"))
            write_json(shots_file, doc)
        # 4) 合并 meta
        merged = _merge_meta(existing if isinstance(existing, dict) else {}, prim_dir and
                             read_json(prim_dir / "meta.json", {}) or {},
                             canon, g["aliases"])
        vcp = merged.get("video_cache_path")
        if vcp:
            merged["video_cache_path"] = vcp.replace(str(prim_dir), str(canon_dir))
        write_json(canon_dir / "meta.json", merged)
        # 5) 写别名表
        add_aliases({a: canon for a in g["aliases"]})
        # 6) 其余目录移入 .trash
        for it in g["members"]:
            d = raw_vdir(it["video_id"])
            if d.resolve() != canon_dir.resolve() and d.is_dir():
                trash.mkdir(parents=True, exist_ok=True)
                shutil.move(str(d), str(trash / d.name))
    result["applied"] = True
    result["trash_dir"] = str(trash)
    return result
