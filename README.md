# dsh-video — 让 LLM 直接“读”视频

把 **bilibili / 本地视频** 变成 agent 可读的结构化索引：带时间戳字幕、词级时间锚点、场景故事板关键帧、弹幕、合集概览；通过 **MCP** 暴露给 DSH，并附带**右侧栏时间轴面板**。

> 面向 [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/deepseek-harness) 的本地插件。作者：siyuanzhai2020-png。

## 能力

| 能力 | 说明 |
|---|---|
| 视频索引 | `open → index → status`：下载/探测 → 字幕优先、缺失才 faster-whisper ASR → 场景切分 + 故事板关键帧 |
| 视频总结 | `outline`（平台章节/自动分段）/ `transcript`（全文）/ `read(t0,t1)`（原文 + 关键帧图片，主模型直接看画面） |
| 精确定位 | ASR `word_timestamps` + 句级重分段：`search` 返回**词级 anchor**（±0.1s） |
| 同音词检索 | 中文查询自动**拼音回退**：`王虹 → 王红/王洪/王宏`、`挂谷 → 挂股/刮骨`（词边界校验，防“围棋/为强”误命中）；标题/标签/简介也参与检索 |
| 合集/分P | `collection`：所有分P标题/时长/索引状态 + 已索引分P的章节目录 |
| 弹幕 | 可选开关（默认关）：`danmaku` 返回区间采样 + 密度（观众反应/高能点） |
| 缓存管理 | 按 `bvid` 归一（URL 与本地文件共用一份索引）；10GB LRU（`cache --prune`，默认 dry-run） |
| 面板 | 右侧栏「视频时间轴」：章节+关键帧时间轴、点击跳读字幕+图、检索跳 anchor、**点击即提问 agent**、删除/清空缓存 |

## 仓库结构

```text
engine/                 Python 引擎（vidx 包 + stdio MCP server）
  vidx/                 open/index/outline/read/search/transcript/collection/danmaku
  tests/                冒烟测试、拼音检索回归、MCP smoke
dsh-video/              DSH 插件：把 vidx MCP server 桥接成 mcp__video__* 工具
dsh-video-panel/        DSH 插件：右侧栏时间轴面板（host 路由 + client 侧栏 tab）
TEST_REPORT.md          本机实测数字与踩坑记录
config.example.json     引擎配置示例（复制为 config.json）
```

## 环境要求

- Windows 10/11（其他平台可用，路径探测已兼容 Linux/macOS）
- Python **3.10+**
- [ffmpeg](https://ffmpeg.org/)（需带 `ffmpeg` 可执行文件；Windows 建议 gyan.dev essentials）
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)（bilibili 下载；放在 PATH 或用配置指定）
- 可选：NVIDIA GPU + CUDA（faster-whisper 使用 CTranslate2，**不需要 torch**；无 GPU 自动回退 CPU）
- DSH（用于插件/面板；仅用 CLI 引擎时可不需要）

## 安装（引擎）

```powershell
git clone <this-repo> dsh-video
cd dsh-video
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# ffmpeg / yt-dlp 二选一：
#   a) 放进 PATH
#   b) config.json 里写绝对路径
copy config.example.json config.json   # 按需填写 ffmpeg / ytdlp / model_dir
```

下载 ASR 模型（CTranslate2 格式；示例 large-v3-turbo，约 1.6GB）：

```powershell
hf download Systran/faster-whisper-large-v3-turbo --local-dir models/faster-whisper-large-v3-turbo
# 或 modelscope / 手动下载后放到 models/faster-whisper-large-v3-turbo
```

自检：

```powershell
cd engine
..\.venv\Scripts\python.exe -m vidx.cli selftest
```

## CLI 快速使用

```powershell
cd engine
$PY = ../../.venv/Scripts/python.exe   # 按实际路径替换

& $PY -m vidx.cli open  "https://www.bilibili.com/video/BV..."   # 结构/时长/分P/字幕状态
& $PY -m vidx.cli index "https://www.bilibili.com/video/BV..."   # 建立索引（下载→ASR→场景→帧）
& $PY -m vidx.cli outline <video_id>
& $PY -m vidx.cli search  <video_id> "王虹"          # 中文自动同音回退
& $PY -m vidx.cli read    <video_id> 111 141 --frames 4
& $PY -m vidx.cli danmaku <video_id> --fetch --from 100 --to 140
& $PY -m vidx.cli cache   --prune --cap-gb 10        # dry-run；--apply 才删
```

输出：缓存默认在 `./_video_cache/`（可 `VIDX_CACHE` 覆盖）。

## 接入 DSH

两个插件目录已包含可以直接注入的 bundle：

- `dsh-video`：创建 `@deepseek-ai/dsh-mcp-client` 桥接，工具名 `mcp__video__*`
- `dsh-video-panel`：右侧栏「视频时间轴」面板

### 方式 A：有 dsh-super-injector（本机开发）

```text
dev_inject_plugin "C:/path/to/dsh-video/dsh-video"
dev_inject_plugin "C:/path/to/dsh-video/dsh-video-panel"
```

然后刷新 Web 页面（client 半身）+ 右侧栏 `+` → 指南 →「视频时间轴」。

### 方式 B：写进 profile（持久）

在 DSH profile 的 `package.json` 里加 link 依赖与 bundles：

```jsonc
{
  "dependencies": {
    "@local/dsh-video": "link:<repo>/dsh-video",
    "@local/dsh-video-panel": "link:<repo>/dsh-video-panel"
  },
  "dsh": { "profile": { "bundles": [
    "@local/dsh-video",
    "@local/dsh-video-panel"
  ]}}
}
```

重启 DSH 生效。`dsh-video` 默认按仓库位置自动定位 `engine/`、`.venv`、`_video_cache/`、`models/`，也可用插件 config 覆盖：

```yaml
- id: dsh-video
  config:
    engineDir: <repo>/engine
    pythonPath: <repo>/.venv/Scripts/python.exe
    cacheDir: <repo>/_video_cache
    modelDir: <repo>/models/faster-whisper-large-v3-turbo
    ffmpegPath: <path-to>/ffmpeg.exe
```

## MCP 工具（9 个）

`mcp__video__open / index / status / outline / read / search / transcript / collection / danmaku`

典型对话：

```text
我：总结 https://www.bilibili.com/video/BV...   → open/index → outline → read → 带 [mm:ss] 总结
我：这个视频哪里提到王虹？                     → search（拼音回退命中 王红/王洪/王宏）→ 给出时间点
我：合集一共几集？都讲什么？                   → collection
我：这段观众什么反应？                         → danmaku(t0,t1) 密度 + 采样
我：点时间轴让 agent 解释这段                   → 面板「问 agent」/「点击即提问」
```

## 右侧栏面板

1. 刷新 Web 页面（client bundle 在页面加载时注册）；
2. 右侧栏 `+` → 指南 →「视频时间轴」；
3. 选视频 → 点时间轴/关键帧跳读；搜索命中后点条目跳到词级 anchor；`问 agent` 把「看这段」发进当前会话。

> 注意：改 host 半边需重启 DSH 生效；**不要对 `dsh-video-panel` 使用 `dev_reload_package`**（会卡住，已踩坑）。client 改动刷新页面即可。

## 已知限制

- 首次索引耗时取决于网络/ASR：本机（RTX 3050 Ti 4GB）42min AV1 视频约 227s（下载 61 + ASR 71 + 场景 38 + 帧 20）。
- ASR 速度受 GPU 电源状态影响（省电模式约 7×，性能模式 20–40×）。
- 场景检测硬件解码仅对 AV1 启用（h264/hevc 走 CPU；`h264_cuvid` 会误判切点，已在代码中禁用）。
- 隐私：`SESSDATA`（登录态字幕/AI 大纲）未接入；所有请求均为匿名。
- 面板 Tab 需要 DSH Web；CLI 引擎可独立使用。

## License

MIT — 见 [LICENSE](LICENSE)。
