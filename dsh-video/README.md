# dsh-video

鎶?**vidx 瑙嗛闃呰寮曟搸**鎺ヨ繘 DSH锛氭湰鎻掍欢涓嶅疄鐜?MCP锛屽彧璐熻矗**骞傜瓑鍦版寕杞藉畼鏂?`@deepseek-ai/dsh-mcp-client` 鏉＄洰**锛岀敱瀹冩妸 vidx 鐨?7 涓伐鍏锋敞鍐屾垚
`mcp__video__open / index / status / outline / read / search / transcript`銆?
## 涓轰粈涔堟槸鎻掍欢锛岃€屼笉鏄墜鍐欎竴琛?patch

| 闇€姹?| 鍋氭硶 |
|---|---|
| 閲嶅惎鍚庝粛鍦?| 浣滀负 bundle 瑁呴厤锛屾瘡娆″惎鍔ㄩ噸鏂版寕杞芥ˉ鎺ユ潯鐩?|
| 涓嶉噸澶嶆寕杞?| `apply()` 鍏堟煡 `ctx.loader.entries()`锛屽悓 `serverName` 宸插瓨鍦ㄥ垯璺宠繃 |
| 鍗歌浇鍗冲噣 | 鍙噴鏀捐嚜宸卞垱寤虹殑鏉＄洰锛屼笉鐣欏菇鐏靛伐鍏?|
| 鍚姩涓嶈鎷栧灝 | `failOnStartupError: false`锛歅ython/妯″瀷缂哄け涔熻兘姝ｅ父鍚姩锛岄娆¤皟鐢ㄦ墠杩?|

## 鍓嶇疆鏉′欢

1. 鏈満宸ヤ綔鍖洪噷鐨?vidx 寮曟搸锛歚harness/video-plugin/engine`锛堢函 Python锛屾棤 Node 鏋勫缓锛夈€?2. 鍚?faster-whisper 鐨?Python 瑙ｉ噴鍣紙榛樿 `.venv`锛夈€?3. ffmpeg锛堥粯璁?`harness/_work/bin/ffmpeg.exe`锛変笌 yt-dlp銆?
## 閰嶇疆锛堝叏閮ㄥ彲閫夛級

| 瀛楁 | 榛樿鍊?| 璇存槑 |
|---|---|---|
| `engineDir` | `鈥?harness/video-plugin/engine` | vidx 鍖呯洰褰曪紙`python -m vidx.mcp_server` 鐨?cwd锛?|
| `pythonPath` | `鈥?.venv/Scripts/python.exe` | 鍚姩 MCP server 鐨勮В閲婂櫒 |
| `serverName` | `video` | MCP 鍛藉悕绌洪棿锛屽伐鍏峰悕 `mcp__video__*` |
| `toolCallTimeoutMs` | `180000` | 鍗曟璋冪敤瓒呮椂锛坮ead 鍚娊甯э級 |
| `cacheDir` | `鈥?harness/_video_cache` | 绱㈠紩缂撳瓨锛圴IDX_CACHE锛?|
| `ffmpegPath` | `鈥?_work/bin/ffmpeg.exe` | ffmpeg锛圴IDX_FFMPEG锛?|
| `modelDir` | `鈥?models/faster-whisper-large-v3-turbo` | ASR 妯″瀷锛圴IDX_MODEL_DIR锛?|
| `autoLoad` | `true` | false = 涓嶆敞鍐?|

## 瑁呴厤 / 鍗歌浇

```
dev_install_package {"dir": "<repo>/dsh-video"}
# 鎴栫敓浜э細dev_build_plugin 涓嶉渶瑕侊紙绾?JS锛夆啋 dev_install_package / plugin_manager install_bundle
```

鍗歌浇锛歚dev_uninject_plugin {"match": "dsh-video"}`锛堟垨 `plugin_manager remove_bundle`锛夈€?
## 宸茬煡鎴愭湰

7 涓伐鍏?鈮?3鈥?k 瀛楃 schema锛堣繙灏忎簬 CATIA 鐨?98 宸ュ叿锛夛紱`read` 杩斿洖鍥剧墖锛?姣忚疆 鈮? 寮犮€佸 960px锛屽浘鐗囬绠楃敱 DSH 鐨?image-offload 绠＄悊銆?

