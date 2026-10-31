# -*- coding: utf-8 -*-
"""MCP stdio 鍐掔儫娴嬭瘯锛氫笉缁忚繃 DSH锛岀洿鎺ユ寜 JSON-RPC 鍜?vidx.mcp_server 瀵硅瘽銆?
鐢ㄦ硶锛堝湪 engine/ 鐩綍涓嬶級::

    python tests/mcp_smoke.py "C:\path\to\video.mp4"
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1]
PY = sys.executable


def call(proc: subprocess.Popen, payload: dict) -> dict:
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("MCP server 娌℃湁鍝嶅簲锛坰tdout 鍏抽棴锛?)
    return json.loads(line)


def main() -> int:
    source = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[2] / "testdata" / "iphone_duo.mp4")
    env = dict(os.environ, PYTHONPATH=str(ENGINE), PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen([PY, "-m", "vidx.mcp_server"], cwd=str(ENGINE), env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            bufsize=1)
    n = 0

    def req(method: str, params: dict | None = None) -> dict:
        nonlocal n
        n += 1
        return call(proc, {"jsonrpc": "2.0", "id": n, "method": method,
                           "params": params or {}})

    try:
        init = req("initialize", {"protocolVersion": "2025-06-18",
                                  "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}})
        print("initialize:", json.dumps(init.get("result"), ensure_ascii=False)[:300])
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        proc.stdin.flush()

        tl = req("tools/list")
        tools = tl["result"]["tools"]
        print(f"tools/list: {len(tools)} -> {[t['name'] for t in tools]}")

        opened = req("tools/call", {"name": "open", "arguments": {"source": source}})
        meta = json.loads(opened["result"]["content"][0]["text"])
        print("open:", meta["meta"]["video_id"], "|", meta["meta"]["title"],
              "|", meta["meta"]["duration_s"], "s |", meta["index"]["status"])
        vid = meta["meta"]["video_id"]

        st = req("tools/call", {"name": "status", "arguments": {"video_id": vid}})
        print("status:", json.loads(st["result"]["content"][0]["text"])["index"]["status"])

        ol = req("tools/call", {"name": "outline", "arguments": {"video_id": vid, "detail": "brief"}})
        outline = json.loads(ol["result"]["content"][0]["text"])
        print("outline:", outline.get("section_source"), "sections=", len(outline.get("sections") or []))

        rd = req("tools/call", {"name": "read", "arguments": {"video_id": vid, "t0": 60, "t1": 180, "frames": 3}})
        content = rd["result"]["content"]
        read_doc = json.loads(content[0]["text"])
        imgs = [c for c in content if c.get("type") == "image"]
        print("read:", read_doc["range"]["label"], "segs=", len(read_doc["segments"]),
              "frames=", len(read_doc["frames"]), "images=", len(imgs),
              "first_image_bytes=", len(imgs[0]["data"]) if imgs else 0)

        se = req("tools/call", {"name": "search", "arguments": {"video_id": vid, "query": "纾侀搧", "k": 3}})
        hits = json.loads(se["result"]["content"][0]["text"])["hits"]
        print("search: hits=", len(hits), "first=", (hits[0]["text"][:60] if hits else None))

        dm = req("tools/call", {"name": "danmaku", "arguments": {"video_id": vid, "t0": 0, "t1": 120, "k": 5}})
        dm_doc = json.loads(dm["result"]["content"][0]["text"])
        print("danmaku: count=", dm_doc.get("count"), "items=", len(dm_doc.get("items") or []))

        col = req("tools/call", {"name": "collection", "arguments": {"source": vid}})
        col_doc = json.loads(col["result"]["content"][0]["text"])
        print("collection: pages=", col_doc.get("total_pages"),
              "indexed=", col_doc.get("indexed_pages"))
        print("SMOKE OK")
        return 0
    finally:
        try:
            proc.terminate()
            err = proc.stderr.read()[-800:]
            if err:
                print("--- stderr tail ---\n" + err, file=sys.stderr)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

