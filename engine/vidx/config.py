# -*- coding: utf-8 -*-
"""全局配置：路径解析优先级 = 环境变量 > config.json > 本机默认值。"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]          # repo root (video-plugin/)
ENGINE_DIR = PROJECT_ROOT / "engine"

DEFAULTS = {
    "cache_dir": str(PROJECT_ROOT / "_video_cache"),
    "cache_cap_gb": 10.0,             # 缓存上限（LRU 淘汰，cache --prune）
    # 留空 = 从 PATH 自动探测；也可在 config.json / VIDX_FFMPEG 指定绝对路径
    "ffmpeg": "",
    "ytdlp": "",
    # faster-whisper 模型目录（CTranslate2 格式；可用 VIDX_MODEL_DIR 覆盖）
    "model_dir": str(PROJECT_ROOT / "models" / "faster-whisper-large-v3-turbo"),
    "model_dir_small": str(PROJECT_ROOT / "models" / "faster-whisper-small"),
    "device": "auto",                 # auto | cuda | cpu
    "compute_type": "auto",           # auto -> cuda:int8_float16, cpu:int8
    "beam_size": 5,
    "vad_filter": True,
    "word_timestamps": True,          # 词级时间戳（用于重分段 + 检索精确定位）
    "resegment_max_s": 12.0,          # 重分段最长时长（句级）
    "resegment_min_s": 0.8,           # 重分段最短时长
    "resegment_pause_s": 0.6,         # 词间停顿超过该值即断句
    "cpu_threads": 0,                 # 0 = 自动
    "idle_unload_s": 600,             # ASR 空闲卸载（秒）
    "language": "auto",               # auto | zh | en | fr ...
    "keep_audio": False,              # ASR 完成后是否保留 16k wav/音频源（默认删，省盘）
    "storyboard_max": 60,             # 每视频故事板关键帧上限
    "scene_threshold": 0.30,          # ffmpeg scene 阈值
    "scene_hw": True,                 # 场景检测用 CUVID 硬解 + 分块（失败自动回退软解）
    "scene_hw_codecs": ["av1"],       # 仅这些编码走硬解（h264/hevc 的 cuvid 解码会误判切点，已实测）
    "scene_chunk_s": 300,             # 硬解分块秒数（规避长进程/硬解偶发崩溃）
    "scene_workers": 3,               # 分块并行数
    "read_frames_default": 4,
    "read_frames_max": 6,
    "download_height": 720,           # bilibili 整片下载高度上限（场景检测用）
    "danmaku_default": False,         # 默认不抓弹幕（可选开关：index(danmaku=true) 或 CLI --danmaku）
    "danmaku_max": 20000,             # 单视频弹幕上限
    "audio_format": 30232,            # bilibili 音频流 id（104k AAC）
    "bilibili_uA": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "request_interval_s": 0.5,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    f = PROJECT_ROOT / "config.json"
    if f.is_file():
        try:
            cfg.update(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    for key, env in (("cache_dir", "VIDX_CACHE"), ("ffmpeg", "VIDX_FFMPEG"),
                     ("ytdlp", "VIDX_YTDLP"), ("model_dir", "VIDX_MODEL_DIR"),
                     ("device", "VIDX_DEVICE")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    return cfg


def cache_dir() -> Path:
    p = Path(load_config()["cache_dir"]).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def workspace() -> Path:
    return PROJECT_ROOT
