# -*- coding: utf-8 -*-
"""ASR 层：faster-whisper（CTranslate2）封装。

设计（依据 2026-10-30 本机实测，见 `_plan_video_plugin/asr/findings.md`）：

* **无 torch**：CTranslate2 自带 CUDA 后端，但 Windows 上需要 cuBLAS/cuDNN 的 DLL。
  这些 DLL 来自 pip 的 `nvidia-*-cu12` wheels，位于
  `site-packages/nvidia/{cublas,cudnn,cuda_nvrtc}/bin`。**必须在 import
  faster_whisper / ctranslate2 之前**把它们注册进 DLL 搜索路径，否则首次推理报
  `RuntimeError: Library cublas64_12.dll is not found or cannot be loaded`。
* **真实推理 probe**：`WhisperModel(..., device="cuda")` 构造成功 ≠ GPU 可用
  （缺 cuBLAS 时构造不报错、首次 encode 才炸；`ctranslate2.get_cuda_device_count()`
  在这种情况下仍返回 1）。所以每档候选加载后都用 1s 静音做一次真实推理。
* **CUDA 卡死防护（实测坑）**：缺 DLL 时第 1 个 cuda 候选会快速报错，但**同一进程内
  再试第 2 个 cuda 候选会永久卡死在 encode**。因此：
  （a）加载前用 ctypes 预检 `cublas64_12.dll` / `cudnn64_9.dll`，不可用就完全跳过 CUDA；
  （b）cuda 候选出现 DLL/初始化类错误后，跳过剩余 cuda 候选，直接降 CPU；
  （c）probe 放在守护线程里跑并 join 超时（默认 120s），保证不挂死宿主进程。
* **回退链**：cuda/int8_float16 → cuda/float16 → cpu/int8（本机实测：GPU 19.7x /
  CPU 3.5x 实时；int8_float16 峰值显存 +1315 MiB，4GB 卡默认选它）。
* **空闲卸载**：faster-whisper 模型常驻会占 1.1–2.1 GB 显存，4GB 卡上不适合永久驻留。
  最后一次调用超过 `idle_unload_s` 后，在 `health()` / `transcribe()` 入口自动卸载，
  下次调用重新加载（实测重载 2–4s）。
* 不依赖 torch / pandas；只用 numpy + faster_whisper + 标准库。
"""
from __future__ import annotations

import gc
import json
import logging
import os
import shutil
import site
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any, Callable

from .config import load_config

log = logging.getLogger("vidx.asr")

# ---------------------------------------------------------------------------
# CUDA DLL 注册：必须发生在 import faster_whisper / ctranslate2 之前。
# 注意 os.add_dll_directory() 的返回值必须保活（句柄被 GC 可能撤销注册），
# 因此这里存进模块级 _DLL_HANDLES。
# ---------------------------------------------------------------------------
_DLL_HANDLES: list[Any] = []
CUDA_DLL_DIRS: list[str] = []


def register_cuda_dlls() -> list[str]:
    """把 pip `nvidia-*-cu12` wheels 的 bin/lib 目录加入 Windows DLL 搜索路径。

    返回实际注册的目录列表（非 Windows 平台返回 []）。
    设置环境变量 `VIDX_ASR_NO_DLL_REGISTER=1` 可跳过（用于验证“不注册会怎样”）。
    """
    if sys.platform != "win32":
        return []

    roots: list[Path] = []
    try:
        for p in list(site.getsitepackages()) + [site.getusersitepackages()]:
            roots.append(Path(p) / "nvidia")
    except Exception:  # pragma: no cover - 极少见的 site 配置
        pass
    roots.append(Path(sys.prefix) / "Lib" / "site-packages" / "nvidia")

    added: list[str] = []
    seen: set[str] = set()
    for root in roots:
        try:
            root = root.resolve()
        except OSError:
            continue
        if not root.is_dir() or str(root) in seen:
            continue
        seen.add(str(root))
        for sub in sorted(root.iterdir()):
            for cand in (sub / "bin", sub / "lib"):
                if not cand.is_dir():
                    continue
                key = str(cand.resolve())
                if key in seen:
                    continue
                seen.add(key)
                try:
                    _DLL_HANDLES.append(os.add_dll_directory(key))  # 必须保活
                    os.environ["PATH"] = key + os.pathsep + os.environ.get("PATH", "")
                    added.append(key)
                except OSError:
                    pass
    return added


if not os.environ.get("VIDX_ASR_NO_DLL_REGISTER"):
    CUDA_DLL_DIRS = register_cuda_dlls()

import numpy as np  # noqa: E402  (faster-whisper 自身依赖 numpy)

FALLBACK_CHAIN: tuple[tuple[str, str], ...] = (
    ("cuda", "int8_float16"),
    ("cuda", "float16"),
    ("cpu", "int8"),
)
PROBE_SECONDS = 1.0
_WIN_NOWINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ASRError(RuntimeError):
    """ASR 初始化 / 推理失败（带失败原因链）。"""


def _now() -> float:
    return time.monotonic()


def _import_whisper_model():
    """延迟 import faster_whisper（确保 DLL 注册先于 ctranslate2 原生库加载）。"""
    from faster_whisper import WhisperModel

    return WhisperModel


# ---------------------------------------------------------------------------
# CUDA 可用性预检（ctypes）
# 背景（实测）：缺 cuBLAS 时第 1 个 cuda 候选会在初次 encode 快速报
# `Library cublas64_12.dll is not found...`，但**同一进程内再试第 2 个 cuda 候选
# 会永久卡死在 encode**（CUDA 状态已被污染）。所以：
#   * 加载前用 ctypes 预检 cublas/cudnn 是否可加载，不可用就直接走 CPU（不碰 CUDA）；
#   * 一旦某个 cuda 候选因 DLL/初始化错误失败，跳过剩余 cuda 候选；
#   * probe 用守护线程跑，带超时，避免把宿主进程一起挂死。
# ---------------------------------------------------------------------------
_CUDA_DLL_NAMES = ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll")


def cuda_dlls_loadable() -> tuple[bool, str | None]:
    """预检 cuBLAS/cuDNN DLL 是否可加载。返回 (ok, error)。

    注意这是“能不能加载 DLL”的检查，不等于 GPU 推理一定可用；
    真正的可用性仍由加载后的 1s 静音 probe 证明。
    """
    if sys.platform != "win32":
        return False, "非 Windows 平台"
    import ctypes

    for name in _CUDA_DLL_NAMES:
        try:
            ctypes.WinDLL(name)  # 走 PATH / os.add_dll_directory 的搜索路径
        except OSError as exc:
            return False, f"{name}: {str(exc)[:200]}"
    return True, None


def _is_cuda_init_error(message: str) -> bool:
    """判断错误是否属于 CUDA 初始化/DLL 类（这类失败后不能继续试 cuda）。"""
    m = message.lower()
    return any(k in m for k in (
        "cublas", "cudnn", "cuda driver", "cuda runtime", "library",
        "not found or cannot be loaded", "no cuda", "cuda error", "cuda failed",
    ))


def _probe_timeout_s() -> float:
    try:
        return float(os.environ.get("VIDX_ASR_PROBE_TIMEOUT_S", "120"))
    except ValueError:
        return 120.0


class ASR:
    """faster-whisper 封装：懒加载 + 设备回退 + 空闲卸载 + 段级时间戳。

    参数优先级：显式传入的**非默认值** > `cfg`（来自 `vidx.config.load_config()`）
    > `vidx.config.DEFAULTS`。由于签名里的默认值是固定字面量（5 / True / 600 / 0），
    “显式传默认值”会被视为未覆盖，此时采用 cfg 中的值。
    """

    def __init__(
        self,
        cfg: dict | None = None,
        model_dir: str | None = None,
        device: str = "auto",
        compute_type: str = "auto",
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = True,
        word_timestamps: bool = True,
        idle_unload_s: int = 600,
        cpu_threads: int = 0,
    ) -> None:
        cfg = dict(cfg or load_config())
        self.cfg: dict[str, Any] = cfg

        self.model_dir = str(model_dir or cfg.get("model_dir") or "")
        self.device = str(device) if device and device != "auto" else str(cfg.get("device", "auto"))
        self.compute_type = (
            str(compute_type) if compute_type and compute_type != "auto"
            else str(cfg.get("compute_type", "auto"))
        )
        self.language = _norm_language(language if language is not None else cfg.get("language", "auto"))
        self.beam_size = int(beam_size if beam_size != 5 else cfg.get("beam_size", 5))
        self.vad_filter = bool(vad_filter if vad_filter is not True else cfg.get("vad_filter", True))
        self.word_timestamps = bool(
            word_timestamps if word_timestamps is not True else cfg.get("word_timestamps", True))
        self.idle_unload_s = float(idle_unload_s if idle_unload_s != 600 else cfg.get("idle_unload_s", 600))
        self.cpu_threads = int(cpu_threads if cpu_threads != 0 else cfg.get("cpu_threads", 0))

        self._lock = threading.RLock()
        self._model = None
        self._loaded_device: str | None = None
        self._loaded_compute: str | None = None
        self._load_s: float | None = None
        self._load_breakdown: dict[str, float] | None = None
        self._cuda_dll_status: tuple[bool, str | None] | None = None
        self._last_use: float | None = None
        self._last_error: str | None = None
        self._last_unload_reason: str | None = None
        self._attempts: list[dict[str, Any]] = []
        self._loads = 0
        self._unloads = 0
        self._idle_unloads = 0
        self._progress_error_logged = False

    # -- 只读属性 ---------------------------------------------------------
    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return Path(self.model_dir).name if self.model_dir else ""

    @property
    def active_device(self) -> str:
        return self._loaded_device or self.device

    @property
    def active_compute_type(self) -> str:
        return self._loaded_compute or self.compute_type

    # -- 内部：候选 / 空闲 / 卸载 -----------------------------------------
    def _candidates(self) -> list[tuple[str, str]]:
        """按优先级返回 (device, compute_type) 候选列表。"""
        dev = (self.device or "auto").lower()
        ct = (self.compute_type or "auto").lower()
        explicit_ct = ct if ct not in ("auto", "") else None
        if dev == "cpu":
            return [("cpu", explicit_ct or "int8")]
        if dev == "cuda":
            # 显式要求 cuda 时仍保留 CPU 兜底（插件运行期要能降级而不是直接崩）
            cands = [("cuda", explicit_ct or "int8_float16")]
            if "cpu/int8" not in [f"{d}/{c}" for d, c in cands]:
                cands.append(("cpu", "int8"))
            return cands
        # auto：实测推荐顺序 int8_float16 -> float16 -> cpu
        if explicit_ct:
            return [("cuda", explicit_ct), ("cpu", "int8")]
        return list(FALLBACK_CHAIN)

    def _idle_s(self) -> float:
        return 0.0 if self._last_use is None else max(0.0, _now() - self._last_use)

    def _unload_locked(self, reason: str) -> None:
        """释放模型引用（调用方需持有 self._lock）。"""
        had_model = self._model is not None
        self._model = None
        self._loaded_device = None
        self._loaded_compute = None
        self._load_s = None
        self._load_breakdown = None
        if not had_model:
            return
        self._unloads += 1
        self._last_unload_reason = reason
        if reason == "idle":
            self._idle_unloads += 1
        gc.collect()  # CTranslate2 在对象析构时释放显存；这里尽早触发
        log.info("ASR 模型已卸载（%s）", reason)

    def _check_idle_locked(self) -> None:
        """空闲超时则卸载（调用方需持有 self._lock）。"""
        if self._model is None or self.idle_unload_s <= 0:
            return
        idle = self._idle_s()
        if idle >= self.idle_unload_s:
            log.info("ASR 空闲 %.1fs ≥ %.0fs，自动卸载释放显存", idle, self.idle_unload_s)
            self._unload_locked("idle")

    def _cuda_status(self) -> tuple[bool, str | None]:
        """缓存 CUDA DLL 预检结果（ctypes 只加载一次）。"""
        if self._cuda_dll_status is None:
            self._cuda_dll_status = cuda_dlls_loadable()
        return self._cuda_dll_status

    def _probe_model(self, model, probe: "np.ndarray") -> None:
        """真实推理 probe（带超时）：1s 静音，失败抛原异常；卡死抛 TimeoutError。

        CUDA 在坏环境下 encode 可能永久卡死（实测：缺 DLL 时第二次 cuda 尝试会挂死），
        这里用守护线程 + join 超时兜底，保证不会把 DSH 宿主进程一起挂死。
        """
        box: dict[str, Any] = {}

        def _run() -> None:
            try:
                list(model.transcribe(probe, language="en", beam_size=1, vad_filter=False)[0])
                box["ok"] = True
            except BaseException as exc:  # noqa: BLE001 - 原样转抛给主线程
                box["error"] = exc

        timeout = _probe_timeout_s()
        th = threading.Thread(target=_run, name="vidx-asr-probe", daemon=True)
        th.start()
        th.join(timeout)
        if th.is_alive():
            raise TimeoutError(f"probe 超过 {timeout:.0f}s 未返回（CUDA 可能卡死）")
        if not box.get("ok"):
            raise box["error"]  # type: ignore[misc]

    def _ensure_loaded_locked(self):
        """按候选链加载模型 + 真实推理 probe；失败逐档降级（调用方持锁）。

        顺序：cuda/int8_float16 → cuda/float16 → cpu/int8（device/compute_type 可覆盖）。
        安全策略（实测结论）：
          * 先用 ctypes 预检 cublas/cudnn，不可用就**完全不碰 CUDA**，直接 CPU；
          * 某个 cuda 候选因 DLL/初始化错误失败后，跳过其余 cuda 候选（第二次 cuda
            encode 可能永久卡死），直接降 CPU；
          * probe 带超时（默认 120s，可用 VIDX_ASR_PROBE_TIMEOUT_S 覆盖）。
        """
        if self._model is not None:
            return self._model
        if not self.model_dir or not Path(self.model_dir).is_dir():
            raise ASRError(f"ASR 模型目录不存在: {self.model_dir!r}")

        WhisperModel = _import_whisper_model()
        probe = np.zeros(int(16000 * PROBE_SECONDS), dtype=np.float32)
        errors: list[str] = []
        candidates = self._candidates()
        skip_cuda = False

        if any(dev == "cuda" for dev, _ in candidates):
            dll_ok, dll_err = self._cuda_status()
            if not dll_ok:
                skipped = [(d, c) for d, c in candidates if d == "cuda"]
                candidates = [(d, c) for d, c in candidates if d != "cuda"]
                for d, c in skipped:
                    self._attempts.append({
                        "device": d, "compute_type": c,
                        "error": f"跳过（CUDA DLL 预检失败）: {dll_err}",
                    })
                log.warning("CUDA DLL 预检失败，跳过 GPU 候选: %s", dll_err)
                if not candidates:
                    raise ASRError(
                        f"CUDA 不可用（{dll_err}）；已注册 DLL 目录={CUDA_DLL_DIRS or '无'}。"
                        f"请改用 device='cpu'，或安装/修复 nvidia-*-cu12 wheels。"
                    )

        for dev, ctype in candidates:
            if dev == "cuda" and skip_cuda:
                continue
            t0 = _now()
            model = None
            try:
                model = WhisperModel(
                    self.model_dir,
                    device=dev,
                    compute_type=ctype,
                    cpu_threads=self.cpu_threads,
                )
                t_ctor = _now() - t0
                t_probe = _now()
                # 真实推理（1s 静音）：只有它能证明 cublas/cuDNN 真的可用
                self._probe_model(model, probe)
                t_probe = _now() - t_probe
                load_s = t_ctor + t_probe
                self._model = model
                self._load_s = load_s
                self._load_breakdown = {"ctor_s": round(t_ctor, 3), "probe_s": round(t_probe, 3)}
                self._loaded_device = dev
                self._loaded_compute = ctype
                self._loads += 1
                self._last_error = None
                self._last_use = _now()
                log.info(
                    "ASR 就绪: %s on %s/%s，加载 %.2fs%s",
                    self.model_name, dev, ctype, load_s,
                    f"（先失败 {len(errors)} 档）" if errors else "",
                )
                return model
            except Exception as exc:  # noqa: BLE001 - 任一候选失败都要降级
                msg = f"{dev}/{ctype}: {type(exc).__name__}: {exc}"
                errors.append(msg)
                self._attempts.append(
                    {"device": dev, "compute_type": ctype,
                     "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
                )
                log.warning("ASR 候选失败 %s", msg)
                model = None
                gc.collect()
                timed_out = isinstance(exc, TimeoutError)
                if dev == "cuda" and (timed_out or _is_cuda_init_error(msg)):
                    skip_cuda = True
                    log.warning("CUDA 初始化类失败：跳过其余 cuda 候选，直接降级 CPU")

        self._last_error = " | ".join(errors) if errors else "未知错误"
        raise ASRError(
            f"ASR 模型加载失败（model={self.model_name}，model_dir={self.model_dir}）：{self._last_error}"
        )

    # -- 内部：音频读取 ---------------------------------------------------
    def _ffmpeg_exe(self) -> str:
        ff = str(self.cfg.get("ffmpeg") or "")
        if ff and Path(ff).is_file():
            return ff
        found = shutil.which("ffmpeg")
        if found:
            return found
        raise ASRError("找不到 ffmpeg（cfg['ffmpeg'] 未配置且 PATH 中不存在），无法解码该音频")

    @staticmethod
    def _read_pcm16_wav(path: Path) -> tuple[np.ndarray, int, int, int] | None:
        """读 16-bit PCM WAV；不是 WAV 或格式不支持时返回 None。"""
        try:
            with wave.open(str(path), "rb") as w:
                return (
                    w.getframerate(),
                    w.getnchannels(),
                    w.getsampwidth(),
                    w.readframes(w.getnframes()),
                )
        except (wave.Error, EOFError, OSError):
            return None

    def _load_audio(self, path: Path) -> tuple[np.ndarray, float]:
        """读取音频为 16 kHz 单声道 float32；非 16k/非 wav 时用 ffmpeg 转码。"""
        raw = self._read_pcm16_wav(path)
        if raw is not None:
            sr, ch, width, frames = raw
            if sr == 16000 and ch == 1 and width == 2:
                audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
                if audio.size:
                    return audio, audio.size / 16000.0
                raise ASRError(f"音频为空: {path}")
            log.info("音频非 16k 单声道（sr=%d ch=%d width=%d），转码: %s", sr, ch, width, path.name)
        return self._load_audio_via_ffmpeg(path)

    def _load_audio_via_ffmpeg(self, path: Path) -> tuple[np.ndarray, float]:
        tmpdir = tempfile.mkdtemp(prefix="vidx_asr_")
        out = os.path.join(tmpdir, "audio16k.wav")
        cmd = [
            self._ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", out,
        ]
        try:
            cp = subprocess.run(
                cmd, capture_output=True, text=True, timeout=1800,
                creationflags=_WIN_NOWINDOW,
            )
            if cp.returncode != 0:
                raise ASRError(f"ffmpeg 解码失败（{path.name}）: {cp.stderr.strip()[:500]}")
            raw = self._read_pcm16_wav(Path(out))
            if raw is None:
                raise ASRError(f"ffmpeg 输出无法读取: {out}")
            sr, ch, width, frames = raw
            if sr != 16000 or ch != 1 or width != 2:
                raise ASRError(f"ffmpeg 输出格式异常 sr={sr} ch={ch} width={width}")
            audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
            if not audio.size:
                raise ASRError(f"音频为空: {path}")
            return audio, audio.size / 16000.0
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # -- 公开 API ---------------------------------------------------------
    def health(self) -> dict:
        """探活：必要时（空闲超时后/首次）加载模型并返回运行状态。

        注意：模型未加载时会触发一次真实加载（2–5s）；调用本身算作“活动”，
        会重置空闲计时。
        """
        with self._lock:
            self._check_idle_locked()
            err: str | None = None
            if self._model is None:
                try:
                    self._ensure_loaded_locked()
                except ASRError as exc:
                    err = str(exc)
            loaded = self._model is not None
            return {
                "ok": loaded,
                "device": self.active_device,
                "compute_type": self.active_compute_type,
                "model": self.model_name,
                "load_s": round(self._load_s, 3) if self._load_s is not None else None,
                "load_breakdown": self._load_breakdown,
                "idle_s": round(self._idle_s(), 1),
                "error": None if loaded else (err or self._last_error),
                # 以下为调试/测试用附加字段
                "model_dir": self.model_dir,
                "language": self.language,
                "loaded": loaded,
                "loads": self._loads,
                "unloads": self._unloads,
                "idle_unloads": self._idle_unloads,
                "idle_unload_s": self.idle_unload_s,
                "last_unload_reason": self._last_unload_reason,
                "attempts": list(self._attempts[-6:]),
                "cuda_dlls_ok": self._cuda_status()[0],
                "cuda_dlls_error": self._cuda_status()[1],
            }

    def transcribe(
        self,
        wav_path: str,
        language: str | None = None,
        progress: Callable[[float, float, str], None] | None = None,
        word_timestamps: bool | None = None,
    ) -> dict:
        """转写一个音频文件（wav/m4a/mp4 等，内部按需 ffmpeg 转 16k）。

        参数
        ----
        wav_path : 音频文件路径
        language : "zh"/"en"/"fr"… 显式指定；None 表示用实例配置（"auto" → 自动检测）
        progress : 每段回调 ``progress(done_s, total_s, text)``，可缺省

        返回
        ----
        dict，字段见模块 docstring / 任务约定：
        segments/language/language_probability/duration_s/device/compute_type/model/
        wall_s/rtf/load_s（另附 text、segment_count、load_this_call_s、audio_s）。
        """
        path = Path(wav_path)
        if not path.is_file():
            raise ASRError(f"音频文件不存在: {path}")
        lang = _norm_language(language if language is not None else self.language)
        word_ts = self.word_timestamps if word_timestamps is None else bool(word_timestamps)

        with self._lock:
            self._check_idle_locked()
            load_this_call_s = 0.0
            if self._model is None:
                t_load = _now()
                self._ensure_loaded_locked()
                load_this_call_s = _now() - t_load
            model = self._model
            assert model is not None  # _ensure_loaded_locked 失败会抛异常

            audio, audio_s = self._load_audio(path)
            total_hint = audio_s

            t0 = _now()
            segments_iter, info = model.transcribe(
                audio,
                language=lang,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                condition_on_previous_text=False,
                temperature=0.0,
                word_timestamps=word_ts,
            )
            try:
                duration = float(getattr(info, "duration", 0.0) or total_hint)
            except Exception:
                duration = total_hint

            segments: list[dict[str, Any]] = []
            text_parts: list[str] = []
            word_total = 0
            for seg in segments_iter:
                text = (seg.text or "").strip()
                if not text:  # 过滤空段（VAD 边界常见）
                    continue
                t0s = round(float(seg.start), 3)
                t1s = round(float(seg.end), 3)
                row: dict[str, Any] = {"t0": t0s, "t1": t1s, "text": text}
                if word_ts:
                    words = []
                    for w in (getattr(seg, "words", None) or []):
                        wt = getattr(w, "word", None) or ""
                        if not wt.strip():
                            continue
                        words.append({"w": wt, "t0": round(float(w.start), 3),
                                      "t1": round(float(w.end), 3),
                                      "p": round(float(getattr(w, "probability", 0.0) or 0.0), 3)})
                    if words:
                        row["words"] = words
                        word_total += len(words)
                segments.append(row)
                text_parts.append(text)
                if progress is not None:
                    try:
                        progress(min(t1s, duration) if duration > 0 else t1s,
                                 duration if duration > 0 else total_hint, text)
                    except Exception:  # noqa: BLE001 - 回调异常不应中断转写
                        self._progress_error_logged = True
                        log.warning("progress 回调异常（已忽略，转写继续）", exc_info=True)

            wall_s = _now() - t0
            self._last_use = _now()
            self._last_error = None
            total = duration if duration > 0 else audio_s
            detected_lang = getattr(info, "language", None) or lang or "?"
            result = {
                "segments": segments,
                "text": " ".join(text_parts),
                "language": detected_lang,
                "language_probability": round(
                    float(getattr(info, "language_probability", 0.0) or 0.0), 4),
                "duration_s": round(float(total), 3),
                "device": self._loaded_device,
                "compute_type": self._loaded_compute,
                "model": self.model_name,
                "wall_s": round(wall_s, 3),
                "rtf": round(wall_s / total, 4) if total > 0 else 0.0,
                "load_s": round(self._load_s, 3) if self._load_s is not None else None,
                "load_this_call_s": round(load_this_call_s, 3),
                "segment_count": len(segments),
                "word_count": word_total,
                "word_timestamps": bool(word_ts),
                "language_forced": lang,
                "audio_s": round(audio_s, 3),
            }
            log.info(
                "ASR 完成: %s | %s/%s | %.1fs 音频 %.2fs wall (%.2fx) %d 段 lang=%s",
                path.name, self._loaded_device, self._loaded_compute,
                total, wall_s, (total / wall_s if wall_s > 0 else 0.0), len(segments), detected_lang,
            )
            return result

    def unload(self) -> None:
        """卸载模型、释放显存（下次 transcribe/health 会自动重新加载）。"""
        with self._lock:
            self._unload_locked("manual")


def _norm_language(lang: Any) -> str | None:
    """把配置里的 "auto"/""/None 统一成 None（= 自动检测）。"""
    if lang is None:
        return None
    s = str(lang).strip()
    if not s or s.lower() in ("auto", "none"):
        return None
    return s


def transcribe_file(
    wav_path: str,
    cfg: dict | None = None,
    language: str | None = None,
) -> dict:
    """一次性转写便捷函数：加载 → 转写 → 卸载（finally 保证释放显存）。"""
    engine = ASR(cfg=cfg, language=language)
    try:
        return engine.transcribe(wav_path, language=language)
    finally:
        engine.unload()


# ---------------------------------------------------------------------------
# CLI：python -m vidx.asr <wav> [--language zh] [--json out.json] [--health]
# 在 engine/ 目录下运行（`vidx` 包所在目录）。
# ---------------------------------------------------------------------------
def _cli_progress(done: float, total: float, text: str) -> None:
    print(f"[{done:8.1f}/{total:8.1f}s] {text}", flush=True)


def main(argv: list[str] | None = None) -> int:
    import argparse

    # 管道/重定向时强制 UTF-8，避免中文被 GBK 控制台截断
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            pass

    ap = argparse.ArgumentParser(
        prog="python -m vidx.asr",
        description="vidx ASR：faster-whisper 转写单个音频文件（GPU 优先，自动降级 CPU）",
    )
    ap.add_argument("wav", help="音频/视频文件路径（wav 优先，其它格式内部用 ffmpeg 转码）")
    ap.add_argument("--language", default=None, help="zh / en / fr …（缺省=自动检测）")
    ap.add_argument("--json", dest="json_path", default=None, help="把完整结果写入该 JSON 文件")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--compute-type", default="auto", help="auto / int8_float16 / float16 / int8 …")
    ap.add_argument("--model", default=None, help="覆盖模型目录")
    ap.add_argument("--idle-unload", type=float, default=None, help="空闲卸载秒数")
    ap.add_argument("--health", action="store_true", help="只探活（health()），不转写")
    ap.add_argument("--no-progress", action="store_true", help="不打印逐段进度")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.no_progress else logging.INFO,
        format="[asr] %(levelname)s %(message)s",
    )

    kwargs: dict[str, Any] = {}
    if args.idle_unload is not None:
        kwargs["idle_unload_s"] = int(args.idle_unload)
    engine = ASR(
        model_dir=args.model,
        device=args.device,
        compute_type=args.compute_type,
        **kwargs,
    )
    try:
        if args.health:
            h = engine.health()
            print(json.dumps(h, ensure_ascii=False, indent=2))
            return 0 if h.get("ok") else 1

        result = engine.transcribe(
            args.wav,
            language=args.language,
            progress=None if args.no_progress else _cli_progress,
        )
        summary = {
            k: result[k]
            for k in ("model", "device", "compute_type", "language", "language_probability",
                      "duration_s", "wall_s", "rtf", "load_s", "segment_count")
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"--- {result['segment_count']} 段 / {len(result['text'])} 字符 ---")
        print(result["text"][:2000])
        if args.json_path:
            out = Path(args.json_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[asr] 结果已写入 {out}")
        return 0
    except ASRError as exc:
        print(f"[asr] ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        engine.unload()


__all__ = [
    "ASR",
    "ASRError",
    "FALLBACK_CHAIN",
    "cuda_dlls_loadable",
    "CUDA_DLL_DIRS",
    "register_cuda_dlls",
    "transcribe_file",
]

if __name__ == "__main__":
    sys.exit(main())
