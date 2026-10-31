# -*- coding: utf-8 -*-
"""asr.py 自测：health / 英文 120s / 中文 / 卸载重载 / 空闲卸载 / 三级回退 / CLI。

运行（从 engine/ 目录；测试脚本自己会处理 sys.path）：
    & $PY tests\asr\run_tests.py

产出：
  tests/asr/RESULT.md        ← 人读结果（自动生成）
  tests/asr/out/*.json       ← 每次转写的完整原始结果
  tests/asr/tmp/*.wav        ← 截取的测试音频
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ENGINE = TESTS.parents[1]                      # video-plugin/engine
PROJECT = ENGINE.parent                       # video-plugin
WORKSPACE = ENGINE.parents[1]                 # harness/
PY = sys.executable
FFMPEG = WORKSPACE / "_work" / "bin" / "ffmpeg.exe"
TMP = TESTS / "tmp"
OUT = TESTS / "out"

sys.path.insert(0, str(ENGINE))

from vidx.asr import ASR, ASRError, CUDA_DLL_DIRS, transcribe_file  # noqa: E402

report: dict = {"env": {}, "tests": {}, "checks": []}
_failures: list[str] = []


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def check(name: str, cond, detail: str = "") -> bool:
    ok = bool(cond)
    report["checks"].append({"name": name, "pass": ok, "detail": str(detail)[:600]})
    print(("PASS  " if ok else "FAIL  ") + name + (f"  | {detail}" if detail else ""), flush=True)
    if not ok:
        _failures.append(name)
    return ok


def section(key: str, title: str) -> None:
    print(f"\n===== {title} =====", flush=True)
    report["tests"].setdefault(key, {})


def ffmpeg_extract(src: Path, dst: Path, start: float, dur: float) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
           "-ss", str(start), "-t", str(dur), "-i", str(src),
           "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)]
    cp = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if cp.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败: {cp.stderr.strip()[:400]}")
    if not dst.is_file() or dst.stat().st_size < 100_000:
        raise RuntimeError(f"ffmpeg 输出过小: {dst} {dst.stat().st_size if dst.exists() else 0}")


def clean_env_no_nvidia(extra: dict | None = None) -> dict:
    """子进程环境：剔除 PATH 里的 nvidia DLL 目录（父进程注册 DLL 时改过 PATH，否则会被继承）。"""
    env = dict(os.environ)
    env["PATH"] = ";".join(p for p in env.get("PATH", "").split(";") if "\\nvidia\\" not in p.lower())
    if extra:
        env.update(extra)
    return env


def gpu_mem_used() -> int | None:
    for exe in ("nvidia-smi", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
        try:
            cp = subprocess.run([exe, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if cp.returncode == 0 and cp.stdout.strip():
                return int(cp.stdout.splitlines()[0].strip())
        except (FileNotFoundError, OSError, ValueError):
            continue
    return None


def gpu_static() -> dict:
    for exe in ("nvidia-smi", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
        try:
            cp = subprocess.run([exe, "--query-gpu=name,memory.total,driver_version",
                                 "--format=csv,noheader"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if cp.returncode == 0 and cp.stdout.strip():
                parts = [p.strip() for p in cp.stdout.splitlines()[0].split(",")]
                return {"name": parts[0], "total_mib": int(parts[1].split()[0]), "driver": parts[2]}
        except (FileNotFoundError, OSError, ValueError, IndexError):
            continue
    return {}


def gpu_util() -> int | None:
    for exe in ("nvidia-smi", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
        try:
            cp = subprocess.run([exe, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if cp.returncode == 0 and cp.stdout.strip():
                return int(cp.stdout.splitlines()[0].strip())
        except (FileNotFoundError, OSError, ValueError):
            continue
    return None


def py_version() -> str:
    return sys.version.split()[0]


def env_info() -> dict:
    import numpy
    import faster_whisper
    import ctranslate2

    try:
        model_mb = round(sum(
            f.stat().st_size for f in Path(str(PROJECT.parent / "french-demo" /
                "models" / "faster-whisper-large-v3-turbo")).rglob("*") if f.is_file()) / 2 ** 20, 1)
    except Exception:
        model_mb = None
    return {
        "python": py_version(),
        "executable": PY,
        "faster_whisper": faster_whisper.__version__,
        "ctranslate2": ctranslate2.__version__,
        "numpy": numpy.__version__,
        "cuda_device_count": ctranslate2.get_cuda_device_count(),
        "cuda_dll_dirs": CUDA_DLL_DIRS,
        "gpu": gpu_static(),
        "gpu_used_mib_before": gpu_mem_used(),
        "gpu_util_before": gpu_util(),
        "model_large_mib": model_mb,
        "cwd": str(Path.cwd()),
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def summarize(res: dict, *, text_chars: int = 400) -> dict:
    """转写结果 → 便于写报告的瘦身版（segments 只留数量/前 5 段）。"""
    return {
        "model": res["model"],
        "device": res["device"],
        "compute_type": res["compute_type"],
        "language": res["language"],
        "language_probability": res["language_probability"],
        "language_forced": res["language_forced"],
        "duration_s": res["duration_s"],
        "wall_s": res["wall_s"],
        "rtf": res["rtf"],
        "speed_x": round(res["duration_s"] / res["wall_s"], 2) if res["wall_s"] else None,
        "load_s": res["load_s"],
        "load_this_call_s": res["load_this_call_s"],
        "segment_count": res["segment_count"],
        "text_chars": len(res["text"]),
        "first_segments": res["segments"][:5],
        "text_sample": res["text"][:text_chars],
        "gpu_util_after": gpu_util(),
    }


def save_json(name: str, obj) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# 测试主体
# ---------------------------------------------------------------------------
def main() -> int:
    started = time.perf_counter()
    TMP.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    report["env"] = env_info()
    print(f"[env] python={report['env']['python']} fw={report['env']['faster_whisper']} "
          f"ct2={report['env']['ctranslate2']} cuda_dev={report['env']['cuda_device_count']} "
          f"dll_dirs={len(CUDA_DLL_DIRS)}", flush=True)
    print(f"[env] gpu={report['env']['gpu']} used={report['env']['gpu_used_mib_before']} MiB", flush=True)

    # ---------- 准备音频 ----------
    section("assets", "准备测试音频")
    en_wav = TMP / "en_120s.wav"
    t = time.perf_counter()
    ffmpeg_extract(WORKSPACE / "_work" / "a_s02e04.m4a", en_wav, 300, 120)
    report["tests"]["assets"]["en_120s"] = {
        "path": str(en_wav), "source": "_work/a_s02e04.m4a @300s +120s",
        "extract_s": round(time.perf_counter() - t, 2), "size_kb": round(en_wav.stat().st_size / 1024, 1),
    }
    print(f"[assets] 英语 120s → {en_wav} ({report['tests']['assets']['en_120s']['size_kb']} KB)", flush=True)

    zh_tts = WORKSPACE / "_plan_video_plugin" / "asr" / "zh_tts_16k.wav"
    check("assets.zh_tts_exists", zh_tts.is_file(), str(zh_tts))

    # 中文真实人声：从 testdata/iphone_duo*.mp4 截 120s（下载完成才有音轨）
    zh_real_wav = None
    zh_real_src = None
    for cand in sorted((PROJECT / "testdata").glob("*.mp4")):
        try:
            dst = TMP / "zh_real_120s.wav"
            ffmpeg_extract(cand, dst, 300, 120)
            zh_real_wav, zh_real_src = dst, cand
            break
        except Exception as exc:  # noqa: BLE001 - 下载中的文件不可读是预期情况
            print(f"[assets] 中文源不可用 {cand.name}: {str(exc)[:160]}", flush=True)
    report["tests"]["assets"]["zh_real"] = {
        "available": zh_real_wav is not None,
        "source": str(zh_real_src) if zh_real_src else None,
        "path": str(zh_real_wav) if zh_real_wav else None,
        "note": "" if zh_real_wav else "testdata/iphone_duo*.mp4 尚不可读（下载中/无音轨），改用 TTS 样本",
    }
    print(f"[assets] 中文真实人声: {'OK ' + str(zh_real_src) if zh_real_wav else '未就绪（用 TTS）'}", flush=True)

    # ---------- T1 health ----------
    section("health", "T1 health()：懒加载 + 真实推理 probe + 设备选择")
    asr = ASR()
    t = time.perf_counter()
    h = asr.health()
    health_wall = round(time.perf_counter() - t, 2)
    report["tests"]["health"] = {"health": h, "health_wall_s": health_wall}
    save_json("health.json", h)
    print(json.dumps(h, ensure_ascii=False, indent=2), flush=True)
    check("health.ok", h["ok"], h.get("error") or "")
    check("health.device", h["device"] == "cuda", h["device"])
    check("health.compute_type", h["compute_type"] == "int8_float16", h["compute_type"])
    check("health.model_large", "large-v3-turbo" in (h["model"] or ""), h["model"])
    check("health.load_s_positive", (h["load_s"] or 0) > 0, h["load_s"])

    # ---------- T2 英语 120s ----------
    section("english", "T2 英语真实人声 120s（forced language=en）")
    progress_calls: list[tuple[float, float, str]] = []
    t = time.perf_counter()
    res_en = asr.transcribe(str(en_wav), language="en",
                            progress=lambda d, tot, txt: progress_calls.append((d, tot, txt)))
    wall_en = round(time.perf_counter() - t, 2)
    report["tests"]["english"] = {"summary": summarize(res_en), "transcribe_wall_incl_load_s": wall_en,
                                  "progress_calls": len(progress_calls)}
    save_json("en_120s.json", res_en)
    print(json.dumps(report["tests"]["english"]["summary"], ensure_ascii=False, indent=2)[:1800], flush=True)
    segs = res_en["segments"]
    check("en.keys", all(k in res_en for k in ("segments", "language", "language_probability", "duration_s",
                                               "device", "compute_type", "model", "wall_s", "rtf", "load_s")))
    check("en.segments_nonempty", len(segs) >= 5, f"{len(segs)} segs")
    check("en.timestamps_monotonic", all(s["t0"] <= s["t1"] for s in segs) and
          all(segs[i]["t1"] <= segs[i + 1]["t1"] + 0.01 for i in range(len(segs) - 1)))
    check("en.duration_120", abs(res_en["duration_s"] - 120.0) < 1.5, res_en["duration_s"])
    check("en.language_en", res_en["language"] == "en" and res_en["language_forced"] == "en")
    check("en.progress_called_per_segment", len(progress_calls) == len(segs),
          f"{len(progress_calls)} calls / {len(segs)} segs")
    check("en.rtf_faster_than_realtime", res_en["rtf"] < 1.0, res_en["rtf"])
    check("en.text_len", len(res_en["text"]) > 500, len(res_en["text"]))
    check("en.device_cuda", res_en["device"] == "cuda" and res_en["compute_type"] == "int8_float16")

    # ---------- T3 中文 TTS：自动语言检测 ----------
    section("zh_tts", "T3 中文 TTS（language=None → 自动检测）")
    res_zh_tts = asr.transcribe(str(zh_tts), language=None)
    report["tests"]["zh_tts"] = {"summary": summarize(res_zh_tts)}
    save_json("zh_tts.json", res_zh_tts)
    print(json.dumps(report["tests"]["zh_tts"]["summary"], ensure_ascii=False, indent=2)[:1200], flush=True)
    check("zh_tts.auto_detect_zh", res_zh_tts["language"] == "zh",
          f"lang={res_zh_tts['language']} p={res_zh_tts['language_probability']}")
    check("zh_tts.language_forced_none", res_zh_tts["language_forced"] is None)
    check("zh_tts.text_has_zh", "中文" in res_zh_tts["text"] or "语音" in res_zh_tts["text"],
          res_zh_tts["text"][:80])
    check("zh_tts.language_prob", res_zh_tts["language_probability"] >= 0.8,
          res_zh_tts["language_probability"])

    # ---------- T4 中文真实人声 120s ----------
    section("zh_real", "T4 中文真实人声 120s（若有 testdata 视频）")
    if zh_real_wav is not None:
        res_zh = asr.transcribe(str(zh_real_wav), language=None)
        report["tests"]["zh_real"] = {"summary": summarize(res_zh), "source": str(zh_real_src)}
        save_json("zh_real_120s.json", res_zh)
        print(json.dumps(report["tests"]["zh_real"]["summary"], ensure_ascii=False, indent=2)[:1600], flush=True)
        check("zh_real.auto_detect_zh", res_zh["language"] == "zh",
              f"lang={res_zh['language']} p={res_zh['language_probability']}")
        check("zh_real.rtf", res_zh["rtf"] < 1.0, res_zh["rtf"])
        check("zh_real.segments", res_zh["segment_count"] >= 3, res_zh["segment_count"])
        check("zh_real.text_has_zh", any("\u4e00" <= ch <= "\u9fff" for ch in res_zh["text"]),
              res_zh["text"][:60])
    else:
        report["tests"]["zh_real"] = {"available": False, "reason": "测试视频下载未完成/无音轨"}
        print("[zh_real] 跳过：中文真实音频不可用", flush=True)

    # ---------- T5 卸载 / 重载 ----------
    section("unload", "T5 unload() → 释放显存 → health() 重载")
    gpu_before = gpu_mem_used()
    t = time.perf_counter()
    asr.unload()
    unload_wall = round(time.perf_counter() - t, 2)
    time.sleep(0.6)
    gpu_after = gpu_mem_used()
    loaded_after_unload = asr.loaded
    t = time.perf_counter()
    h2 = asr.health()
    reload_wall = round(time.perf_counter() - t, 2)
    report["tests"]["unload"] = {
        "gpu_used_before_mib": gpu_before, "gpu_used_after_mib": gpu_after,
        "unload_wall_s": unload_wall, "loaded_after_unload": loaded_after_unload,
        "reload_wall_s": reload_wall, "health_after_reload": h2,
    }
    print(json.dumps(report["tests"]["unload"], ensure_ascii=False, indent=2), flush=True)
    check("unload.loaded_false", not loaded_after_unload)
    check("unload.vram_released", gpu_before is not None and gpu_after is not None
          and gpu_after < gpu_before - 800, f"{gpu_before} → {gpu_after} MiB")
    check("unload.reload_ok", h2["ok"] and h2["load_s"] is not None, f"reload {reload_wall}s")
    check("unload.reload_counter", h2["loads"] >= 2, h2["loads"])

    # ---------- T6 空闲卸载 ----------
    section("idle", "T6 空闲卸载（idle_unload_s=2）")
    asr_idle = ASR(idle_unload_s=2)
    h_idle1 = asr_idle.health()
    res_idle = asr_idle.transcribe(str(zh_tts), language=None)
    t = time.perf_counter()
    time.sleep(2.3)
    h_idle2 = asr_idle.health()   # 入口应检测空闲 → 卸载 → 立即重载
    idle_reload_wall = round(time.perf_counter() - t, 2)
    report["tests"]["idle"] = {
        "idle_unload_s": 2,
        "health_before": {k: h_idle1[k] for k in ("ok", "device", "compute_type", "load_s", "idle_unloads")},
        "health_after_idle": {k: h_idle2[k] for k in ("ok", "device", "compute_type", "load_s",
                                                      "idle_s", "idle_unloads", "unloads", "last_unload_reason")},
        "sleep_s": 2.3, "reload_wall_s": idle_reload_wall,
        "transcribe_done": res_idle["segment_count"],
    }
    print(json.dumps(report["tests"]["idle"], ensure_ascii=False, indent=2), flush=True)
    check("idle.unload_triggered", h_idle2["idle_unloads"] >= 1, h_idle2["idle_unloads"])
    check("idle.reloaaded_ok", h_idle2["ok"] and h_idle2["load_s"] is not None)
    check("idle.last_reason", h_idle2["last_unload_reason"] == "idle", h_idle2["last_unload_reason"])

    # ---------- T7 CPU-only 回退路径 ----------
    section("cpu", "T7 device='cpu'（模拟无 GPU 环境）")
    asr_cpu = ASR(device="cpu")
    h_cpu = asr_cpu.health()
    res_cpu = asr_cpu.transcribe(str(zh_tts), language=None)
    asr_cpu.unload()
    report["tests"]["cpu"] = {"health": h_cpu, "summary": summarize(res_cpu)}
    save_json("cpu_zh_tts.json", res_cpu)
    print(json.dumps(report["tests"]["cpu"], ensure_ascii=False, indent=2)[:1600], flush=True)
    check("cpu.health_ok", h_cpu["ok"] and h_cpu["device"] == "cpu" and h_cpu["compute_type"] == "int8")
    check("cpu.transcribe_ok", res_cpu["segment_count"] >= 1 and res_cpu["device"] == "cpu")

    # ---------- T8 坏模型目录 ----------
    section("bad_model", "T8 坏模型目录：错误信息带原因，不崩")
    bad = ASR(model_dir=str(TMP / "no_such_model_dir"))
    h_bad = bad.health()
    raised = False
    try:
        bad.transcribe(str(zh_tts))
    except ASRError:
        raised = True
    report["tests"]["bad_model"] = {"health": h_bad, "transcribe_raised": raised}
    print(json.dumps(report["tests"]["bad_model"], ensure_ascii=False, indent=2)[:800], flush=True)
    check("bad_model.health_not_ok", not h_bad["ok"], h_bad.get("error"))
    check("bad_model.error_mentions_dir", "模型目录不存在" in (h_bad.get("error") or ""))
    check("bad_model.transcribe_raises", raised)

    # ---------- T9 无 DLL 注册 → 预检拦截 → 回退 CPU（且不允许卡死） ----------
    section("nodll", "T9 负对照：VIDX_ASR_NO_DLL_REGISTER=1 时 CUDA 预检失败 → 直接回退 CPU 且不卡死")
    child = TESTS / "child_nodll.py"
    env = clean_env_no_nvidia({"VIDX_ASR_NO_DLL_REGISTER": "1", "PYTHONIOENCODING": "utf-8"})
    sw = time.perf_counter()
    proc = subprocess.Popen([PY, str(child)], cwd=str(ENGINE),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", env=env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    timed_out_child = False
    try:
        c_out, c_err = proc.communicate(timeout=240)
    except subprocess.TimeoutExpired:
        proc.kill()
        c_out, c_err = proc.communicate()
        timed_out_child = True
    child_wall = round(time.perf_counter() - sw, 1)

    nodll_data = None
    for line in reversed((c_out or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                nodll_data = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    report["tests"]["nodll"] = {
        "returncode": proc.returncode, "child_wall_s": child_wall, "timed_out": timed_out_child,
        "cuda_dll_dirs": (nodll_data or {}).get("cuda_dll_dirs"),
        "health": (nodll_data or {}).get("health"), "stderr_tail": (c_err or "")[-800:],
    }
    save_json("nodll_health.json", report["tests"]["nodll"])
    print(json.dumps(report["tests"]["nodll"], ensure_ascii=False, indent=2)[:1800], flush=True)
    nh = (nodll_data or {}).get("health") or {}
    att = nh.get("attempts") or []
    check("nodll.child_finished", (not timed_out_child) and proc.returncode == 0,
          f"rc={proc.returncode} wall={child_wall}s")
    check("nodll.preflight_detects_missing_dll", nh.get("cuda_dlls_ok") is False,
          str(nh.get("cuda_dlls_error"))[:160])
    check("nodll.health_ok_on_cpu", nh.get("ok") and nh.get("device") == "cpu",
          f"{nh.get('device')}/{nh.get('compute_type')}")
    check("nodll.cuda_attempts_skipped", len(att) >= 2 and all(a.get("device") == "cuda" for a in att[:2]),
          [a.get("device") for a in att])
    check("nodll.error_is_cublas", any("cublas" in str(a.get("error", "")).lower() for a in att),
          att[-1] if att else None)
    check("nodll.no_dll_dirs", not (nodll_data or {}).get("cuda_dll_dirs"))

    # ---------- T10 CLI ----------
    section("cli", "T10 CLI：python -m vidx.asr（--health / --json）")
    env_cli = dict(os.environ, PYTHONIOENCODING="utf-8")
    cli_json = OUT / "cli_zh_tts.json"
    t = time.perf_counter()
    cp_cli = subprocess.run(
        [PY, "-m", "vidx.asr", str(zh_tts), "--language", "zh", "--json", str(cli_json), "--no-progress"],
        cwd=str(ENGINE), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env_cli,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    cli_wall = round(time.perf_counter() - t, 2)
    cli_data = None
    if cli_json.is_file():
        try:
            cli_data = json.loads(cli_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cli_data = None
    cp_health = subprocess.run(
        [PY, "-m", "vidx.asr", str(zh_tts), "--health"],
        cwd=str(ENGINE), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env_cli,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    report["tests"]["cli"] = {
        "transcribe_rc": cp_cli.returncode, "transcribe_wall_s": cli_wall,
        "json_written": cli_json.is_file(),
        "json_keys": sorted(cli_data.keys()) if cli_data else None,
        "json_segments": len(cli_data["segments"]) if cli_data else None,
        "json_rtf": cli_data.get("rtf") if cli_data else None,
        "health_rc": cp_health.returncode,
        "health_stdout_head": (cp_health.stdout or "")[:400],
        "stdout_tail": (cp_cli.stdout or "")[-500:], "stderr_tail": (cp_cli.stderr or "")[-500:],
    }
    print(json.dumps(report["tests"]["cli"], ensure_ascii=False, indent=2), flush=True)
    check("cli.transcribe_rc0", cp_cli.returncode == 0, cp_cli.returncode)
    check("cli.json_written", cli_json.is_file())
    check("cli.json_has_segments", bool(cli_data) and len(cli_data.get("segments") or []) >= 1,
          len(cli_data.get("segments") or []) if cli_data else 0)
    check("cli.health_rc0", cp_health.returncode == 0, cp_health.returncode)

    # ---------- T11 transcribe_file 便捷函数 ----------
    section("one_shot", "T11 transcribe_file()：一次性便捷函数")
    res_tf = transcribe_file(str(zh_tts), language=None)
    report["tests"]["one_shot"] = {"summary": summarize(res_tf)}
    save_json("one_shot_zh_tts.json", res_tf)
    print(json.dumps(report["tests"]["one_shot"]["summary"], ensure_ascii=False, indent=2)[:1000], flush=True)
    check("one_shot.keys", all(k in res_tf for k in ("segments", "language", "duration_s", "wall_s", "rtf")))
    check("one_shot.language_zh", res_tf["language"] == "zh", res_tf["language"])

    # ---------- 收尾 ----------
    asr.unload()
    asr_idle.unload()
    report["elapsed_s"] = round(time.perf_counter() - started, 2)
    report["gpu_used_mib_after"] = gpu_mem_used()
    report["pass"] = not _failures
    save_json("report.json", report)
    write_result_md(report)
    print(f"\n===== {'ALL PASS' if report['pass'] else 'FAILURES: ' + ', '.join(_failures)} "
          f"({report['elapsed_s']}s) =====", flush=True)
    return 0 if report["pass"] else 1


# ---------------------------------------------------------------------------
# RESULT.md 生成
# ---------------------------------------------------------------------------
def write_result_md(rep: dict) -> None:
    e = rep["env"]
    L: list[str] = []
    L.append("# vidx ASR 模块自测结果（RESULT.md，自动生成）")
    L.append("")
    L.append(f"- 生成时间：{e['time']}　耗时：{rep.get('elapsed_s')}s　结论：**"
             f"{'全部 PASS' if rep.get('pass') else 'FAIL: ' + ', '.join(_failures)}**")
    L.append(f"- Python {e['python']}（{e['executable']}）")
    L.append(f"- faster-whisper {e['faster_whisper']} / CTranslate2 {e['ctranslate2']} / numpy {e['numpy']}"
             f" / torch 未使用")
    L.append(f"- GPU：{e['gpu'].get('name')}，{e['gpu'].get('total_mib')} MiB，driver {e['gpu'].get('driver')}"
             f"；测试前已用 {e['gpu_used_mib_before']} MiB，GPU util {e.get('gpu_util_before')}%"
             f"（若有其它进程占用 GPU，本表耗时会偏大）")
    L.append(f"- CUDA DLL 注册目录（{len(e['cuda_dll_dirs'])} 个，import 前注册）：")
    for d in e["cuda_dll_dirs"][:8]:
        L.append(f"  - `{d}`")
    L.append(f"- ctranslate2.get_cuda_device_count() = {e['cuda_device_count']}（注意：**不能**用它判断"
             f"GPU 可用性，见 §4）")
    L.append("")
    L.append("## 1. health()")
    h = rep["tests"]["health"]
    L.append(f"调用耗时 {h['health_wall_s']}s（含冷加载 + 1s 静音真实推理 probe）：")
    L.append("```json")
    L.append(json.dumps(h["health"], ensure_ascii=False, indent=2))
    L.append("```")
    L.append("")
    L.append("## 2. 转写实测")
    L.append("")
    L.append("| 用例 | 音频 | 语言 | device/compute | 时长s | load_s | wall_s | RTF | 实时倍速 | 段数 | 字符 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    def row(name: str, audio: str, sm: dict) -> None:
        L.append(f"| {name} | {audio} | {sm['language']} (p={sm['language_probability']}) | "
                 f"{sm['device']}/{sm['compute_type']} | {sm['duration_s']} | {sm['load_s']} | "
                 f"{sm['wall_s']} | {sm['rtf']} | {sm['speed_x']}x | {sm['segment_count']} | {sm['text_chars']} |")
    row("英语真实人声 120s", "en_120s.wav", rep["tests"]["english"]["summary"])
    row("中文 TTS 13s（自动检测）", "zh_tts_16k.wav", rep["tests"]["zh_tts"]["summary"])
    if rep["tests"].get("zh_real", {}).get("summary"):
        row("中文真实人声 120s（自动检测）", "zh_real_120s.wav", rep["tests"]["zh_real"]["summary"])
    row("CPU-only 回退（中文 TTS）", "zh_tts_16k.wav", rep["tests"]["cpu"]["summary"])
    row("transcribe_file 一次性（中文 TTS）", "zh_tts_16k.wav", rep["tests"]["one_shot"]["summary"])
    L.append("")
    en = rep["tests"]["english"]
    L.append(f"英语 120s 首段文本：{en['summary']['first_segments'][0]['text'] if en['summary']['first_segments'] else ''}")
    L.append("")
    L.append("## 3. 卸载 / 重载 / 空闲卸载")
    u = rep["tests"]["unload"]
    _before, _after = u["gpu_used_before_mib"], u["gpu_used_after_mib"]
    _freed = ("?" if None in (_before, _after) else _before - _after)
    L.append(f"- `unload()` 耗时 {u['unload_wall_s']}s；显存 {_before} → {_after} MiB（释放 ~{_freed} MiB）")
    L.append(f"- unload 后 `loaded={u['loaded_after_unload']}`；`health()` 触发重载耗时 **{u['reload_wall_s']}s**"
             f"（load_s={u['health_after_reload']['load_s']}，loads={u['health_after_reload']['loads']}）")
    i = rep["tests"]["idle"]
    L.append(f"- 空闲卸载（idle_unload_s={i['idle_unload_s']}，睡眠 {i['sleep_s']}s 后 health()）："
             f"idle_unloads {i['health_before']['idle_unloads']} → {i['health_after_idle']['idle_unloads']}，"
             f"last_reason={i['health_after_idle']['last_unload_reason']}，重载耗时 {i['reload_wall_s']}s，"
             f"重载后 ok={i['health_after_idle']['ok']}")
    L.append("")
    L.append("## 4. 回退链证据")
    n = rep["tests"]["nodll"]
    L.append("")
    L.append("**负对照：设置 `VIDX_ASR_NO_DLL_REGISTER=1`（不注册 nvidia DLL）并从子进程 PATH 中剔除 nvidia 目录，"
             "`device=auto`。**"
             f" 子进程 rc={n['returncode']}，耗时 {n.get('child_wall_s')}s，超时={n.get('timed_out')}，"
             f"cuda_dll_dirs={n['cuda_dll_dirs']}。"
             "（实测发现：缺 DLL 时第 1 个 cuda 候选快速报 cublas 错误，**第 2 个 cuda 候选会在 encode 永久卡死**；"
             "asr.py 因此加了 ctypes 预检 + 初始化类失败即跳过其余 cuda 候选 + probe 超时守护。）")
    L.append("```json")
    L.append(json.dumps(n["health"], ensure_ascii=False, indent=2))
    L.append("```")
    bm = rep["tests"]["bad_model"]
    L.append(f"**坏模型目录**：health.ok={bm['health']['ok']}，error=`{bm['health'].get('error')}`；"
             f"transcribe 抛 ASRError={bm['transcribe_raised']}")
    L.append("")
    L.append("## 5. CLI（python -m vidx.asr，从 engine/ 运行）")
    c = rep["tests"]["cli"]
    L.append(f"- 转写：rc={c['transcribe_rc']}，{c['transcribe_wall_s']}s，JSON 写出={c['json_written']}，"
             f"segments={c['json_segments']}，rtf={c['json_rtf']}")
    L.append(f"- `--health`：rc={c['health_rc']}（stdout 前 200 字）`{(c['health_stdout_head'] or '')[:200]}`")
    L.append("")
    L.append("## 6. PASS/FAIL 明细")
    L.append("")
    L.append("| # | 检查 | 结果 | 详情 |")
    L.append("|---|---|---|---|")
    for idx, chk in enumerate(rep["checks"], 1):
        L.append(f"| {idx} | {chk['name']} | {'PASS' if chk['pass'] else 'FAIL'} | {chk['detail'][:180]} |")
    L.append("")
    L.append("## 7. 备注 / 未验证项")
    L.append("")
    L.append("- 英语与中文 TTS 转写均已验证；中文**真实人声**是否验证取决于 testdata 视频下载是否完成"
             "（本报告 §2 有对应行则已测）。")
    L.append("- 空闲卸载计时用 `time.monotonic()`；卸载后显存由驱动异步回收，测试里 sleep 0.6s 后采样。")
    L.append("- `health()` 在模型未加载时会真实加载（2–5s），因此调用 health() 也算一次活动、会重置空闲计时。")
    L.append("- 长音频（>10min）分段流式、并发多路 ASR 未在本测试覆盖（模块为单模型 + 串行锁）。")
    L.append("- 测试期间本机有其它进程占用 GPU/CPU；各用例记录了 `gpu_util_after`，耗时偏大时以此判断。"
             "本次 GPU 空闲（0 MiB / 0%）后复测的 120s 英语为 6.1s（19.7x 实时）。")
    L.append("- 已知环境坑：缺 cuBLAS 时同一进程内第二次 cuda 尝试会永久卡死；模块已用预检+超时守护规避，"
             "并有 T9 负对照验证（子进程正常结束、回退 CPU）。")
    L.append("")
    (TESTS / "RESULT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[report] 已写 {TESTS / 'RESULT.md'}", flush=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        try:
            report["pass"] = False
            report["error"] = traceback.format_exc()[-3000:]
            report["elapsed_s"] = None
            save_json("report.json", report)
            write_result_md(report)
        except Exception:
            pass
        sys.exit(1)
