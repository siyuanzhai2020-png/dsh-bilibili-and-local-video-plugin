# -*- coding: utf-8 -*-
"""字幕解析、检索、自动分段、SRT 导出。"""
from __future__ import annotations

import re
from pathlib import Path

_TS_SRT = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
_TS_VTT = _TS_SRT
_TS_LRC = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")
_ASS_TAG = re.compile(r"\{[^}]*\}")
_ASS_LINE = re.compile(r"^(Dialogue|Comment):\s*(.*)$", re.IGNORECASE)


def _to_ms(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def _clean(text: str) -> str:
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _mk(t0: float, t1: float, text: str) -> dict | None:
    text = _clean(text)
    if not text or t1 <= t0:
        return None
    return {"t0": round(t0, 3), "t1": round(t1, 3), "text": text}


def parse_srt(content: str) -> list[dict]:
    segments: list[dict] = []
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n").replace("\r", "\n"))
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip() != ""]
        if not lines:
            continue
        ti = None
        for i, line in enumerate(lines[:3]):
            if "-->" in line:
                ti = i
                break
        if ti is None:
            continue
        left, _, right = lines[ti].partition("-->")
        a = _TS_SRT.search(left)
        b = _TS_SRT.search(right)
        if not a or not b:
            continue
        text = " ".join(lines[ti + 1:])
        seg = _mk(_to_ms(*a.groups()), _to_ms(*b.groups()), text)
        if seg:
            segments.append(seg)
    return segments


def parse_ass(content: str) -> list[dict]:
    segments: list[dict] = []
    fmt = ["Layer", "Start", "End", "Style", "Name", "MarginL", "MarginR",
           "MarginV", "Effect", "Text"]
    in_events = False
    for raw in content.splitlines():
        line = raw.strip()
        if line.lower().startswith("[") and line.lower().startswith("[events"):
            in_events = True
            continue
        if line.startswith("[") and in_events:
            in_events = False
        if not in_events:
            continue
        if line.lower().startswith("format:"):
            fmt = [x.strip() for x in line.split(":", 1)[1].split(",")]
            continue
        m = _ASS_LINE.match(line)
        if not m:
            continue
        parts = m.group(2).split(",", len(fmt) - 1)
        if len(parts) < len(fmt):
            continue
        row = dict(zip(fmt, parts))
        try:
            t0 = _to_ms(*re.split(r"[:.]", row["Start"].strip()))
            t1 = _to_ms(*re.split(r"[:.]", row["End"].strip()))
        except Exception:
            continue
        text = _ASS_TAG.sub("", row.get("Text", "")).replace("\\N", " ").replace("\\n", " ")
        seg = _mk(t0, t1, text)
        if seg:
            segments.append(seg)
    return segments


def parse_vtt(content: str) -> list[dict]:
    segments: list[dict] = []
    for block in re.split(r"\n\s*\n", content.replace("\r\n", "\n")):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines or "-->" not in block:
            continue
        for i, line in enumerate(lines):
            if "-->" in line:
                left, _, right = line.partition("-->")
                a = _TS_VTT.search(left)
                b = _TS_VTT.search(right)
                if not a or not b:
                    break
                text = " ".join(lines[i + 1:])
                seg = _mk(_to_ms(*a.groups()), _to_ms(*b.groups()), text)
                if seg:
                    segments.append(seg)
                break
    return segments


def parse_lrc(content: str) -> list[dict]:
    rows = []
    for line in content.splitlines():
        m = _TS_LRC.match(line.strip())
        if not m:
            continue
        t = int(m.group(1)) * 60 + int(m.group(2))
        if m.group(3):
            t += int(m.group(3).ljust(3, "0")) / 1000.0
        rows.append((t, line.strip()[m.end():]))
    rows.sort()
    out = []
    for i, (t, text) in enumerate(rows):
        t1 = rows[i + 1][0] if i + 1 < len(rows) else t + 4.0
        seg = _mk(t, min(t1, t + 10.0), text)
        if seg:
            out.append(seg)
    return out


def load_subtitle_file(path: str) -> list[dict]:
    p = Path(path)
    content = p.read_text(encoding="utf-8-sig", errors="replace")
    ext = p.suffix.lower()
    if ext == ".ass" or ext == ".ssa":
        segs = parse_ass(content)
    elif ext == ".vtt":
        segs = parse_vtt(content)
    elif ext == ".lrc":
        segs = parse_lrc(content)
    else:
        segs = parse_srt(content)
        if not segs:
            segs = parse_ass(content) or parse_vtt(content)
    segs.sort(key=lambda s: s["t0"])
    return segs


# ---------------- 词级时间戳 -> 句/段级重分段 ----------------

_SENT_END = set(".!?。！？…")


def words_text(words: list[dict]) -> str:
    """把 whisper 的 word token 拼回文本（英文 token 自带前导空格，中文逐字无空格）。"""
    return "".join(w.get("w") or "" for w in words).strip()


def resegment(raw_segments: list[dict], max_s: float = 12.0, min_s: float = 0.8,
              pause_s: float = 0.6) -> list[dict]:
    """用词级时间戳把 ASR 原始段切成「句级」小段（无词数据时返回空）。

    切分条件（任一）：句末标点且已足够长 / 词间停顿 >= pause_s / 段长 >= max_s。
    长 ASR 段（实测有 386s）会被切细，检索/引用精度从“整段”提升到“一句”。
    """
    words: list[dict] = []
    out: list[dict] = []
    # 按 ASR 原始段边界切分：中文原始段已是 ~2s 短语级，不能再跨段合并成 12s 大块
    for seg in raw_segments or []:
        words = [w for w in (seg.get("words") or []) if (w.get("w") or "").strip()]
        if not words:
            if (seg.get("text") or "").strip():
                out.append({"t0": round(float(seg["t0"]), 3), "t1": round(float(seg["t1"]), 3),
                            "text": seg["text"]})
            continue
        words.sort(key=lambda w: float(w.get("t0") or 0.0))
        cur: list[dict] = []
        start = float(words[0]["t0"])
        for i, w in enumerate(words):
            cur.append(w)
            end = float(w["t1"])
            nxt = words[i + 1] if i + 1 < len(words) else None
            gap = (float(nxt["t0"]) - end) if nxt else 0.0
            wtxt = (w.get("w") or "").strip()
            sent_end = bool(wtxt) and wtxt[-1] in _SENT_END
            dur = end - start
            if nxt is None or dur >= max_s or (sent_end and dur >= min_s) or gap >= pause_s:
                text = words_text(cur)
                if text:
                    out.append({"t0": round(start, 3), "t1": round(end, 3), "text": text,
                                 "words": cur})
                cur = []
                start = float(nxt["t0"]) if nxt else end
    out.sort(key=lambda s: s["t0"])
    return out


def _char_spans(seg: dict) -> list[tuple[int, int, float, float]]:
    """段内每个词的字符区间（相对于 seg['text']）与时间。"""
    words = seg.get("words") or []
    joined = "".join(w.get("w") or "" for w in words)
    lead = len(joined) - len(joined.lstrip())
    spans = []
    pos = 0
    for w in words:
        raw = w.get("w") or ""
        a, b = pos - lead, pos - lead + len(raw)
        pos += len(raw)
        spans.append((a, b, float(w.get("t0") or 0.0), float(w.get("t1") or 0.0)))
    return spans


def _anchor_in_segment(seg: dict, query: str) -> dict | None:
    """在段内定位查询短语，返回词级精确时间；找不到返回 None。"""
    q = (query or "").strip()
    if not q:
        return None
    low = seg["text"].lower()
    idx = low.find(q.lower())
    if idx < 0:
        return None
    spans = _char_spans(seg) if seg.get("words") else []
    if not spans:
        return {"t0": seg["t0"], "t1": seg["t1"], "text": seg["text"][idx:idx + len(q)],
                "mode": "segment"}
    end = idx + len(q) - 1
    hit = [s for s in spans if s[1] > idx and s[0] <= end and s[0] >= 0]
    if not hit:
        return None
    return {"t0": round(min(s[2] for s in hit), 3),
            "t1": round(max(s[3] for s in hit), 3),
            "text": seg["text"][idx:idx + len(q)], "mode": "word"}


def refine_anchor(segments: list[dict], lo: int, hi: int, query: str) -> dict | None:
    """在命中窗口内找查询短语的词级时间锚点（整串优先，其次最长 token）。"""
    cands = [query] + sorted({t for t in _tokens(query) if len(t) >= 2},
                             key=len, reverse=True)
    for q in cands:
        for j in range(lo, hi + 1):
            a = _anchor_in_segment(segments[j], q)
            if a:
                return a
    return None


def write_srt(segments: list[dict], path: str) -> str:
    def ts(t: float) -> str:
        ms = int(round(t * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, seg in enumerate(segments, 1):
        lines += [str(i), f"{ts(seg['t0'])} --> {ts(seg['t1'])}", seg["text"], ""]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def fmt_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------------- 检索 ----------------

_STOP = set("""the a an and or of to in on at for with from by is are was were be been being
this that these those it its as not but if then than so we you he she they i me my our your
就 的 了 是 在 和 也 我 你 他 她 它 们 这 那 有 不 就 都 而 及 与 很 太 吧 呢 啊 吗 哦 嗯 一个 什么 怎么 可以
我们 你们 他们 这个 那个 就是 现在 时候 已经 没有 这样 那样 还是 其实 觉得 应该 知道 看到 一下 这么 那么
如果 可能 需要 因为 所以 但是 然后 一些 这些 那些 比较 非常 真的 感觉 东西 问题 时候 一个 两个 这种 那种
自己 大家 这里 那里 怎么样 为什么 可不是 有点 有点 稍微 特别 起来 出来 过来 进去 之后 之前 以后 以前""".split())


def _tokens(text: str) -> list[str]:
    text = text.lower()
    toks = re.findall(r"[a-z0-9][a-z0-9'’\-]*", text)
    cjk = re.findall(r"[\u4e00-\u9fff]+", text)
    for run in cjk:
        if len(run) == 1:
            toks.append(run)
        else:
            toks.extend(run[i:i + 2] for i in range(len(run) - 1))
    return [t for t in toks if t not in _STOP and len(t) > 0]


def search_segments(segments: list[dict], query: str, k: int = 8,
                    max_window_s: float = 90.0) -> list[dict]:
    """轻量 BM25 风格检索：英文词 + 中文 bigram；命中后合并相邻段并带上下文。"""
    if not segments or not query.strip():
        return []
    q_tokens = _tokens(query)
    if not q_tokens:
        return []
    seg_tokens = [_tokens(s["text"]) for s in segments]
    n = len(segments)
    df: dict[str, int] = {}
    for toks in seg_tokens:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    avg_len = max(1.0, sum(len(t) for t in seg_tokens) / n)
    k1, b = 1.5, 0.75
    scored = []
    q_raw = query.strip().lower()
    for i, (seg, toks) in enumerate(zip(segments, seg_tokens)):
        if not toks:
            continue
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for qt in set(q_tokens):
            f = tf.get(qt, 0)
            if not f:
                continue
            idf = 1.0 + (n - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5)
            score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * len(toks) / avg_len))
        if q_raw and len(q_raw) >= 2 and q_raw in seg["text"].lower():
            score *= 1.6
        if score > 0:
            scored.append((score, i))
    if not scored:
        return []
    scored.sort(reverse=True)

    picked = []
    used = set()
    max_merge_segments = 12
    for score, i in scored:
        if i in used:
            continue
        # 合并相邻命中段（间隔 <=3s），但有窗口时长/段数上限，避免整集被吞掉
        lo = hi = i
        group = [i]
        changed = True
        while changed:
            changed = False
            if (hi + 1 < n and hi + 1 not in used
                    and segments[hi + 1]["t0"] - segments[hi]["t1"] <= 3.0
                    and segments[hi + 1]["t1"] - segments[lo]["t0"] <= max_window_s
                    and (hi - lo) < max_merge_segments):
                hi += 1
                group.append(hi)
                changed = True
            elif (lo - 1 >= 0 and lo - 1 not in used
                    and segments[lo]["t0"] - segments[lo - 1]["t1"] <= 3.0
                    and segments[hi]["t1"] - segments[lo - 1]["t0"] <= max_window_s
                    and (hi - lo) < max_merge_segments):
                lo -= 1
                group.append(lo)
                changed = True
        # 上下文 ±1
        ctx_lo = max(0, lo - 1)
        ctx_hi = min(n - 1, hi + 1)
        group.extend([ctx_lo, ctx_hi])
        group = sorted(set(group))
        for j in group:
            used.add(j)
        text = " ".join(segments[j]["text"] for j in group)
        anchor = refine_anchor(segments, lo, hi, query)
        picked.append({
            "score": round(score, 3),
            "t0": segments[lo]["t0"], "t1": segments[hi]["t1"],
            "anchor": anchor,
            "text": text if len(text) <= 900 else text[:900] + "…",
            "segment_indices": group,
        })
        if len(picked) >= k:
            break
    picked.sort(key=lambda x: x["t0"])
    return picked


def pinyin_search(segments: list[dict], query: str, k: int = 8,
                  max_window_s: float = 90.0) -> list[dict]:
    """拼音同音检索：解决 ASR 把“王虹”写成王红/王洪/王宏 这类问题。

    只对含 CJK 的查询启用；用词级时间戳把命中映射回具体时间锚点。
    命中项带 `match="pinyin"` 与 `matched`（ASR 实际写法），便于模型判断可信度。
    """
    from . import pinyin

    if not segments or not query.strip() or not pinyin.AVAILABLE:
        return []
    if not pinyin.has_cjk(query):
        return []
    q_py = pinyin.text_pinyin(query)
    if len(q_py) < 2:
        return []
    matches: dict[int, tuple[float, float, str]] = {}
    for i, seg in enumerate(segments):
        words = seg.get("words") or []
        idx_map: list[int] | None
        word_spans: list[tuple[int, int]] = []
        if words:
            py_parts: list[str] = []
            idx_map = []
            cursor = 0
            for wi, w in enumerate(words):
                py = pinyin.text_pinyin(w.get("w") or "")
                if not py:
                    continue
                py_parts.append(py)
                idx_map.extend([wi] * len(py))
                word_spans.append((cursor, cursor + len(py)))
                cursor += len(py)
            py_text = "".join(py_parts)
        else:
            py_text = pinyin.text_pinyin(seg.get("text") or "")
            idx_map = None
        # 词边界校验：防止“围棋(weiqi)”误命中“为强(weiqiang)”这种词内子串
        pos = py_text.find(q_py)
        valid = False
        while pos >= 0:
            end = min(pos + len(q_py) - 1, len(py_text) - 1)
            if not idx_map:
                valid = True
                break
            wi = idx_map[pos]
            wj = idx_map[min(end, len(idx_map) - 1)]
            if pos == word_spans[wi][0] and end + 1 == word_spans[wj][1]:
                valid = True
                break
            pos = py_text.find(q_py, pos + 1)
        if not valid:
            continue
        if idx_map:
            wi = idx_map[pos]
            wj = idx_map[min(end, len(idx_map) - 1)]
            t0 = float(words[wi]["t0"])
            t1 = float(words[wj]["t1"])
            matched = "".join((w.get("w") or "") for w in words[wi:wj + 1]).strip()
        else:
            t0, t1 = float(seg["t0"]), float(seg["t1"])
            matched = (seg.get("text") or "")[:40]
        matches[i] = (t0, t1, matched)
    if not matches:
        return []
    n = len(segments)
    picked: list[dict] = []
    used: set[int] = set()
    for i in sorted(matches):
        if i in used:
            continue
        group = [i]
        used.add(i)
        lo = hi = i
        anchor_pts = [matches[i]]
        # 合并相邻的同音命中段，避免一句一条刷屏
        while (hi + 1 < n and hi + 1 in matches and hi + 1 not in used
               and segments[hi + 1]["t0"] - segments[hi]["t1"] <= 3.0
               and segments[hi + 1]["t1"] - segments[lo]["t0"] <= max_window_s
               and (hi - lo) < 12):
            hi += 1
            used.add(hi)
            group.append(hi)
            anchor_pts.append(matches[hi])
        while (lo - 1 >= 0 and lo - 1 in matches and lo - 1 not in used
               and segments[lo]["t0"] - segments[lo - 1]["t1"] <= 3.0
               and segments[hi]["t1"] - segments[lo - 1]["t0"] <= max_window_s
               and (hi - lo) < 12):
            lo -= 1
            used.add(lo)
            group.append(lo)
            anchor_pts.append(matches[lo])
        ctx = sorted(set(group + [max(0, lo - 1), min(n - 1, hi + 1)]))
        text = " ".join(segments[j]["text"] for j in ctx)
        at0 = round(min(p[0] for p in anchor_pts), 3)
        at1 = round(max(p[1] for p in anchor_pts), 3)
        matched = " / ".join(dict.fromkeys(p[2] for p in anchor_pts))[:120]
        picked.append({
            "score": 0.0,
            "t0": segments[lo]["t0"], "t1": segments[hi]["t1"],
            "anchor": {"t0": at0, "t1": at1, "text": matched, "mode": "pinyin"},
            "text": text if len(text) <= 900 else text[:900] + "…",
            "segment_indices": ctx,
            "match": "pinyin",
            "matched": matched,
        })
        if len(picked) >= k:
            break
    picked.sort(key=lambda x: x["t0"])
    return picked


# ---------------- 自动分段 ----------------

_CJK = re.compile(r"[\u4e00-\u9fff]")


def _keywords(segments: list[dict], top: int = 4) -> list[str]:
    counts: dict[str, int] = {}
    for seg in segments:
        for tok in _tokens(seg["text"]):
            if len(tok) < 2 and not _CJK.match(tok):
                continue
            counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [w for w, c in ranked[:top] if c >= 2]


def _first_sentence(text: str, limit: int = 60) -> str:
    text = text.strip()
    m = re.split(r"(?<=[。！？.!?])\s*", text, maxsplit=1)
    s = (m[0] if m else text).strip()
    return s[:limit] + ("…" if len(s) > limit else "")


def auto_sections(segments: list[dict], total: float, target: int = 8) -> list[dict]:
    if not segments:
        return []
    target = max(1, min(target, 30))
    desired = total / target
    # 候选边界：段间静音 >0.8s 的“后一段起点”
    gaps = []
    for i in range(1, len(segments)):
        gap = segments[i]["t0"] - segments[i - 1]["t1"]
        if gap >= 0.8:
            gaps.append((segments[i]["t0"], gap))
    bounds = [0.0]
    for pos in range(1, target):
        want = pos * desired
        near = [g for g in gaps if abs(g[0] - want) < desired * 0.6]
        pick = max(near, key=lambda g: g[1])[0] if near else want
        if pick > bounds[-1] + 5:
            bounds.append(pick)
    bounds.append(total)
    sections = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        group = [s for s in segments if a <= s["t0"] < b] or \
                [s for s in segments if s["t0"] >= a][:1]
        if not group:
            continue
        kws = _keywords(group)
        # title_hint 用首句更可读；关键词留给模型做主题判断
        title_hint = _first_sentence(group[0]["text"], 36)
        sections.append({
            "idx": len(sections) + 1,
            "t0": round(a, 2), "t1": round(min(b, total), 2),
            "title_hint": title_hint,
            "first": _first_sentence(group[0]["text"]),
            "last": _first_sentence(group[-1]["text"]),
            "keywords": kws,
            "segments": len(group),
        })
    return sections


def sections_from_chapters(segments: list[dict], chapters: list[dict], total: float) -> list[dict]:
    out = []
    for i, ch in enumerate(chapters):
        a = ch.get("t0", 0.0)
        b = ch.get("t1") or (chapters[i + 1].get("t0", total) if i + 1 < len(chapters) else total)
        group = [s for s in segments if a <= s["t0"] < b]
        if not group:
            continue
        kws = _keywords(group)
        out.append({
            "idx": i + 1, "t0": round(a, 2), "t1": round(min(b, total), 2),
            "title": ch.get("title") or "",
            "title_hint": ch.get("title") or "·".join(kws[:3]),
            "first": _first_sentence(group[0]["text"]),
            "last": _first_sentence(group[-1]["text"]),
            "keywords": kws, "segments": len(group),
        })
    return out


def segments_in_range(segments: list[dict], t0: float, t1: float) -> list[dict]:
    return [s for s in segments if s["t1"] > t0 and s["t0"] < t1]
