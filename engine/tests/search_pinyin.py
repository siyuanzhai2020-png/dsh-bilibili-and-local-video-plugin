# -*- coding: utf-8 -*-
"""拼音同音检索回归测试（ASR 同音词：王虹→王红/王洪/王宏，挂谷→挂股/刮骨）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidx import pinyin, transcript  # noqa: E402


def words_of(text: str, t0: float, step: float = 0.3) -> list[dict]:
    out = []
    for i, ch in enumerate(text):
        a = round(t0 + i * step, 2)
        out.append({"w": ch, "t0": a, "t1": round(a + step, 2), "p": 1.0})
    return out


def main() -> int:
    ok = True
    if not pinyin.AVAILABLE:
        print("SKIP: pypinyin 未安装")
        return 0

    cases = [("王虹", "王红", True), ("挂谷", "挂股", True), ("挂谷", "刮骨", True),
             ("王宏", "王洪", True)]
    for q, text, want in cases:
        got = pinyin.text_pinyin(q) == pinyin.text_pinyin(text)
        print(f"pinyin({q}) == pinyin({text}) -> {got}")
        ok &= got == want

    segs = [
        {"t0": 10.0, "t1": 12.0, "text": "王红就是因为在调和分析领域的工作",
         "words": words_of("王红就是因为在调和分析领域的工作", 10.0)},
        {"t0": 20.0, "t1": 21.5, "text": "三维挂股猜想的证明",
         "words": words_of("三维挂股猜想的证明", 20.0)},
        {"t0": 30.0, "t1": 31.0, "text": "围棋讲审美讲大局观",
         "words": words_of("围棋讲审美讲大局观", 30.0)},
        {"t0": 40.0, "t1": 41.0, "text": "为强还是不强",
         "words": words_of("为强还是不强", 40.0)},
    ]
    hits = transcript.pinyin_search(segs, "王虹", k=4)
    print("pinyin_search(王虹):", [(h["t0"], h.get("matched")) for h in hits])
    ok &= any(abs(h["t0"] - 10.0) < 1.0 and h.get("matched") == "王红" for h in hits)

    hits2 = transcript.pinyin_search(segs, "挂谷猜想", k=4)
    print("pinyin_search(挂谷猜想):", [(h["t0"], h.get("matched")) for h in hits2])
    ok &= any(abs(h["t0"] - 20.0) < 1.0 for h in hits2)

    # 词边界防误伤：围棋(weiqi) 不应命中“为强(weiqiang)”内部
    hits3 = transcript.pinyin_search(segs, "围棋", k=4)
    print("pinyin_search(围棋):", [(h["t0"], h.get("matched")) for h in hits3])
    ok &= all(h["t0"] < 35 for h in hits3)  # 只命中 30s 的真正“围棋”

    hits4 = transcript.pinyin_search(segs, "苹果", k=4)
    print("pinyin_search(苹果):", hits4)
    ok &= hits4 == []

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
