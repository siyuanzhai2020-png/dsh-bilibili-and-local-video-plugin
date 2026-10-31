# @local/dsh-video-panel

DSH Web 鍙充晶鏍忕殑銆岃棰戞椂闂磋酱銆嶉潰鏉匡紙M3锛夈€傞厤鍚?`@local/dsh-video`锛圡CP 宸ュ叿锛変娇鐢ㄣ€?
## 鍔熻兘

- 瑙嗛閫夋嫨锛氬垪鍑?`_video_cache` 閲屽凡绱㈠紩鐨勮棰戯紙鏍囬/鏃堕暱/娈垫暟/闀滃ご/寮瑰箷锛夈€?- 鏃堕棿杞达細绔犺妭鍧?+ 60 涓叧閿抚鍒荤偣锛涚偣鍑讳换鎰忎綅缃烦杞紙绾㈣壊绔栫嚎 = 褰撳墠浣嶇疆锛夈€?- 褰撳墠绐楀彛锛氳鏃堕棿鐐瑰墠鍚?15s 鐨勫瓧骞曞師鏂?+ 4 寮犲叧閿抚鍥剧墖銆?- 妫€绱細杈撳叆鍏抽敭璇?鈫?鍛戒腑鍒楄〃锛堝甫璇嶇骇閿氱偣鏃堕棿锛夛紝鐐瑰嚮璺冲埌閿氱偣銆?- 澶嶅埗寮曠敤锛氭妸褰撳墠绐楀彛鐨勬枃瀛楀鍒舵垚 `[mm:ss] 瀛楀箷鈥 寮曠敤鏍煎紡銆?
## 鎵撳紑鏂瑰紡

1. 鎵撳紑涓€涓細璇濓紙鍙充晶鏍忛渶瑕?Session 涓婁笅鏂囷級锛?2. 鍙充晶鏍忛《閮ㄧ殑 **+** 鈫?鎸囧崡閲岄€夈€岃棰戞椂闂磋酱銆嶏紱
3. 闈㈡澘鍐呴€夋嫨瑙嗛鍗冲彲銆?
> 棣栨娉ㄥ叆/鏇存柊 client 鍗婅韩鍚庨渶瑕佸埛鏂颁竴娆￠〉闈紙client bundle 娉ㄥ唽鍦ㄩ〉闈㈠姞杞芥椂瀹屾垚锛夈€?
## 缁撴瀯

- `lib/index.js`锛坔ost锛夛細`/video-panel/api`銆乣/video-panel/frame` 璺敱锛涙暟鎹叏閮ㄨ浆缁?  `python -m vidx.panel_api`锛坋ngine 鐨?pipeline锛夛紝涓嶉噸澶嶅疄鐜版绱?閲嶅垎娈?璇嶇骇閿氱偣銆?- `lib/client.js`锛坈lient锛夛細鎵嬪啓 CJS + ModuleLoader 鍖呰锛涙敞鍐屽彸渚ф爮 tab 绫诲瀷
  `dsh-video-timeline`銆乥ody/title slot锛坘ey=`@local/dsh-video-panel`锛変笌 guide 鍏ュ彛銆?- 鏈満娌℃湁鍙敤鐨?tsc/tsdown锛坮untime 涓嶅惈婧愮爜 checkout锛夛紝鎵€浠?lib 涓烘墜鍐欎骇鐗┿€佹棤鏋勫缓姝ラ锛?  鏀归€昏緫鐩存帴鏀?`lib/*.js`锛宍dev_inject_plugin` 鐑敞鍏ュ嵆鍙紙client 鏀瑰姩闇€鍒锋柊椤甸潰锛夈€?
## 渚濊禆

- `@local/dsh-video`锛圡CP锛岀储寮曟暟鎹潵婧愶級涓?`@local/dsh-video-panel`锛堟湰鍖咃級閮藉湪 profile 鐨勬敞鍏ユ竻鍗曢噷銆?- host 渚х敤 `ctx.webServer`锛堝墠缂€璺敱锛変笌 `ctx.workingDirectory`锛堝畾浣?workspace 涓嬬殑
  `video-plugin/engine`銆乣.venv`銆乣_video_cache`锛夈€?
