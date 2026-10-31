# -*- coding: utf-8 -*-
"""临时诊断：不注册 DLL + PATH 去掉 nvidia 目录时，看卡在哪一步（60s 后 dump 栈并退出）。"""
import faulthandler
import json
import sys
import time
from pathlib import Path

faulthandler.dump_traceback_later(60, exit=True)

ENGINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ENGINE))

import logging  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from vidx.asr import ASR, CUDA_DLL_DIRS  # noqa: E402

print("dll_dirs:", CUDA_DLL_DIRS, flush=True)
print("PATH nvidia entries:", [p for p in __import__("os").environ.get("PATH", "").split(";") if "nvidia" in p.lower()], flush=True)

t = time.time()
engine = ASR()
print(f"ASR() ctor {time.time() - t:.2f}s", flush=True)
t = time.time()
health = engine.health()
print(f"health() {time.time() - t:.2f}s", flush=True)
print(json.dumps(health, ensure_ascii=False, indent=2)[:1200], flush=True)
engine.unload()
