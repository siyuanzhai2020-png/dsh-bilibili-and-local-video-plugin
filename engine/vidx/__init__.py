# -*- coding: utf-8 -*-
"""vidx — 视频阅读引擎（bilibili / 本地视频 → 结构化可读索引）。

模块布局（M0）::

    config.py      路径/默认配置（ffmpeg、yt-dlp、模型、缓存、设备）
    store.py       缓存目录、video_id、JSON 读写
    media.py       ffmpeg/ffprobe 封装（探测、音轨抽取、字幕抽取、抽帧）
    asr.py         faster-whisper（DLL 注册 / 设备回退 / 空闲卸载）
    sources.py     BilibiliSource / LocalSource
    scenes.py      场景切分 + 故事板关键帧
    transcript.py  字幕解析 / 检索 / 自动分段
    pipeline.py    open/index/outline/read/search 编排
    cli.py         命令行入口

只依赖：faster-whisper(CTranslate2) + 标准库 + requests（bilibili API）。
"""
__version__ = "0.1.0"
PIPELINE_VERSION = 1
