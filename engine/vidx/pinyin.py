# -*- coding: utf-8 -*-
"""中文拼音检索（ASR 同音词兜底）。

把汉字逐字转成无声调拼音并拼成连续串，用于匹配 ASR 的同音误写：

- 王虹 / 王红 / 王洪 / 王宏 → wanghong
- 挂谷 / 挂股 / 刮骨 / 挂骨 → guagu

只在查询里含 CJK 且普通检索没有更好命中时作为补充/锚点升级使用；
pypinyin 是可选依赖，缺失时本模块返回空结果（不影响主流程）。
"""
from __future__ import annotations

from functools import lru_cache

try:  # 可选依赖
    from pypinyin import lazy_pinyin as _lazy_pinyin

    AVAILABLE = True
except Exception:  # pragma: no cover - 未安装时静默降级
    _lazy_pinyin = None
    AVAILABLE = False


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff"


@lru_cache(maxsize=65536)
def _char_pinyin(ch: str) -> str:
    if not AVAILABLE or not _is_cjk(ch):
        return ""
    try:
        return "".join(_lazy_pinyin(ch))
    except Exception:
        return ""


@lru_cache(maxsize=4096)
def text_pinyin(text: str) -> str:
    """文本 → 无声调拼音串（含 CJK 转写；ASCII 字母数字保留小写；标点/空白丢弃）。"""
    if not AVAILABLE or not text:
        return ""
    out = []
    for ch in text:
        if _is_cjk(ch):
            out.append(_char_pinyin(ch))
        elif ch.isascii() and ch.isalnum():
            out.append(ch.lower())
    return "".join(out)


def has_cjk(text: str) -> bool:
    return any(_is_cjk(ch) for ch in (text or ""))
