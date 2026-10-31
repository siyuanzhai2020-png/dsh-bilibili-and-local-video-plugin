# -*- coding: utf-8 -*-
"""负对照子进程（T9 用）：不注册 nvidia DLL 时 import，验证 device=auto 会降级到 CPU。

由 run_tests.py 以 `VIDX_ASR_NO_DLL_REGISTER=1` 启动；stdout 最后一行输出 JSON。
"""
import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2]   # video-plugin/engine
sys.path.insert(0, str(ENGINE))

from vidx.asr import ASR, CUDA_DLL_DIRS  # noqa: E402


def main() -> int:
    engine = ASR()
    health = engine.health()
    print(json.dumps({"cuda_dll_dirs": CUDA_DLL_DIRS, "health": health}, ensure_ascii=False))
    engine.unload()
    return 0 if health.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
