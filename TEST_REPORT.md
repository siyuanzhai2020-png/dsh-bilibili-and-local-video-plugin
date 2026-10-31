# vidx 娴嬭瘯鎶ュ憡锛圡0/M1锛?026-10-30锛?
> 鏁板瓧鍏ㄩ儴鏉ヨ嚜鏈満鐪熷疄杩愯锛歊TX 3050 Ti Laptop 4GB / i5-12500H / 32GB RAM銆?> 娴嬭瘯绱犳潗涓虹敤鎴锋寚瀹氱殑涓や釜 bilibili 瑙嗛锛?> 1. `BV1xrnz6gEVD` 鎶?涓囨锛屼細鍧忓悧锛焛Phone Duo娣卞害璇勬祴锛?492s锛屼腑鏂囷紝5 涓钩鍙扮珷鑺傦級
> 2. `BV17q9EBEE9w` [Wifies/鐢熻倝] 涓嶅瓨鍦ㄧ殑涓栫晫 [鍏ㄩ泦]锛坧1 2509s锛岃嫳鏂囷紱p2 7355s锛?> 瑙嗛 1 鍏堢敤 yt-dlp 鐖彇涓烘湰鍦版枃浠讹紙143MB 720p锛夊厖褰撯€滅绾胯棰戔€濄€?
## 1. 鐜

| 椤?| 鍊?|
|---|---|
| Python / ASR | .venv 3.10.6锛沠aster-whisper 1.2.1 + CTranslate2 4.8.2锛?*鏃?torch**锛?|
| GPU | RTX 3050 Ti Laptop 4096MiB锛宒river 592.82锛堟祴璇曟湡闂存闈㈠崰鐢?~1.1GB锛?|
| ffmpeg | `_work/bin/ffmpeg.exe` 7.1 essentials锛涙湰鏈?*鏃?ffprobe**锛屾帰娴嬬敤 `ffmpeg -i` 瑙ｆ瀽瀹炵幇 |
| yt-dlp | 2026.10.21锛堝尶鍚嶅彲涓?1080P DASH锛涙湰娴嬭瘯鐢?720p锛?|
| 缂撳瓨 | `<workspace>/_video_cache/`锛涢煶棰?ASR 鍚庡嵆鍒狅紙榛樿锛?|

## 2. 绂荤嚎瑙嗛 A锛氭棤瀛楀箷璺緞锛坴ideo 1锛屼腑鏂?24.9min锛?
| 姝ラ | 瀹炴祴 | 澶囨敞 |
|---|---|---|
| 涓嬭浇锛坹t-dlp 720p 鍚堝苟锛?| 143.2MB / ~76s | 涔嬪悗浣滀负鏈湴鏂囦欢娴嬭瘯绂荤嚎璺緞 |
| 鎺㈡祴 | <0.1s | 1280x720 / 29.97fps / AAC 48k stereo / 鏃犲瓧骞曡建 / 鏃犲唴宓岀珷鑺?|
| sidecar 鍏冩暟鎹悎骞?| <0.1s | `<name>.info.json` 鈫?鏍囬/UP涓?鏍囩/绠€浠?+ **5 涓钩鍙扮珷鑺?* |
| 闊抽鎶藉彇 16k mono | ~3s | 46.6MB wav锛圓SR 鍚庡凡鍒犻櫎锛?|
| **ASR锛坙arge-v3-turbo, cuda/int8_float16锛?* | **~198s锛圧TF 0.133 鈮?7.5脳锛?* | 715 娈碉紱涓枃閫愬瓧璐ㄩ噺濂斤紙闄勫綍 A锛?|
| 鍦烘櫙鍒囧垎锛坒fmpeg scene 0.30锛?| **27.9s** | 376 闀滃ご锛圓SL 涓綅 鈮?.5s锛?|
| 鏁呬簨鏉?60 甯э紙960px锛?| **~33s** | 60 寮?PNG 鈮?7MB |
| 棣栨绱㈠紩鎬昏€楁椂 | **~4.3min** | 涓嶅惈涓嬭浇锛涗簩娆¤闂?<0.2s |
| outline | 0.1s | 5 骞冲彴绔犺妭锛堝紑鍦?鏍稿績鐥涚偣锛?灞忓箷涓庨摪閾?浣跨敤浣撻獙涓庤蒋浠堕€傞厤/Duo鐨勫奖鍍忎綋楠岋級 |
| read(176鈥?05s, 3 甯? | ~1s | 15 娈靛瓧骞?+ 2 寮犲叧閿抚锛堝唴瀹瑰凡鍦ㄥ璇濅腑鑲夌溂鏍稿锛?|
| search("纾侀搧") | 0.1s | 3 涓獥鍙ｏ紙176.8鈥?04.8 / 207.1鈥?31.5 / 233.1鈥?56.3s锛夛紝甯︽渶杩戝叧閿抚 |

> 鎬ц兘澶囨敞锛氭湰娆¤繍琛?GPU 澶勪簬 SW Power Cap 浣庨鐘舵€侊紙SM 780MHz / 17W锛夛紝ASR 浠?~7.5脳锛?> 鍚屾満姝ゅ墠鍩哄噯锛堥珮鏃堕挓锛夎揪 31.8脳銆傚洜姝?ASR 閫熷害鎸?**7脳锛堢渷鐢碉級/ 30脳锛堟€ц兘锛?* 涓ゆ。鐞嗚В銆?> 瑙嗛 2 鐨勮嫳鏂?ASR 瀹為檯杈惧埌 24.3脳锛堝彛鎾█鐤?+ GPU 宸插崌棰戯級銆?
## 3. 绂荤嚎瑙嗛 B锛氬瓧骞曚紭鍏堣矾寰勶紙鎶?ASR 寰楀埌鐨?SRT 灏佽杩?MKV 妯℃嫙鈥滃甫瀛楀箷鐨勭绾胯棰戔€濓級

| 姝ラ | 瀹炴祴 |
|---|---|
| remux mp4 + srt 鈫?mkv锛堝惈 `-metadata:s:s:0 language=chi`锛?| ~2s锛?42.3MB |
| 鎺㈡祴 | 璇嗗埆鍑?1 鏉″唴宓屽瓧骞曡建锛坰ubrip/chi锛?|
| 鏂囨湰 | **鐩存帴瑙ｆ瀽鍐呭祵瀛楀箷 715 娈碉紝闆?ASR** |
| 鍦烘櫙妫€娴?| 22.3s锛?76 闀滃ご锛?|
| 鏁呬簨鏉?60 甯?| ~19.7s |
| **绱㈠紩鎬昏€楁椂** | **42.3s**锛坴s 鏃犲瓧骞曡矾寰?4.3min锛岀害 6脳 鍔犻€燂級 |

## 4. 鍦ㄧ嚎 bilibili 鍏ㄦ祦绋嬶紙video 2 p1锛岃嫳鏂?41.8min锛屽尶鍚嶆棤瀛楀箷锛?
| 姝ラ | 瀹炴祴 | 澶囨敞 |
|---|---|---|
| yt-dlp 涓嬭浇鏁寸墖 720p | 107.9MB / **60.6s** | full.mp4 淇濈暀鍦ㄧ紦瀛橈紙read 鎶藉抚鐢級 |
| 闊抽鎶藉彇 16k | 5.8s | ASR 鍚庡垹闄?|
| **ASR锛堣嫳鏂囷紝鑷姩妫€娴?en锛宲鈮?.0锛?* | **103.4s锛圧TF 0.041 鈮?24.3脳锛?* | 253 娈碉紱鍙ｆ挱瀵嗗害浣?+ VAD 鐢熸晥 |
| 鍦烘櫙鍒囧垎 | **233.4s** | 197 闀滃ご锛汚V1 720p30锛岃蒋瑙ｆ槸鐡堕锛?*M2-1 浼樺寲鍚?37.7s锛岃 搂4.1**锛?|
| 鏁呬簨鏉?60 甯?| ~38s | |
| **绱㈠紩鎬昏€楁椂** | **443.1s 鈮?7.4min** | 涓嬭浇+ASR+鍦烘櫙+甯?|
| outline | 0.1s | 9 涓嚜鍔ㄥ垎娈碉紙0鈥?71s 鈥?2258鈥?509s锛?|
| search("crossroads turn left") | 0.1s | 3 涓懡涓紙49.8鈥?13.4s / 2359.2鈥?367.8s / 2370.8鈥?439.5s锛夛紱**M2-2 鍚庡甫璇嶇骇 anchor 2365.61s** |
| read(1228鈥?290s, 4 甯? | ~2s | 4 娈靛瓧骞?+ 4 甯э紙Minecraft 鐗╁搧鏍忕敾闈紝宸插湪瀵硅瘽涓倝鐪兼牳瀵癸級 |

### 4.1 M2-1锛氬満鏅娴嬩紭鍖栵紙2026-10-30 杩藉姞锛屽凡鍚堝叆榛樿璺緞锛?
鐡堕鏍瑰洜锛歷ideo 2 鏄?**AV1** 720p30锛屾湰鏈鸿蒋浠惰В鐮佷粎 ~20脳锛?2min 鍏夎В鐮佸氨 ~127s锛沗-hwaccel cuda`锛堝抚鑷姩鍥炴嫹锛?瀹炴祴鏃犳敹鐩娿€傚彲琛屾柟妗堟槸 **CUVID 纭В + 鍥哄畾 300s 鍒嗗潡 + 3 璺苟琛?*锛堝垏鐐逛粛鐢ㄥ叏鍒嗚鲸鐜?scene 鎵撳垎锛岀簿搴︿笉闄嶏級銆?
| 鏂规锛堝悓鏈哄娴嬶級 | 42min AV1 鍏ㄧ墖 | 25min H.264 鍏ㄧ墖 | 鍒囩偣涓€鑷存€?|
|---|---|---|---|
| 杞В鍏ㄧ墖锛堝師璺緞锛?| 233.4s | 27.9s | 鍩虹嚎 |
| **CUVID 鍒嗗潡骞惰锛堥粯璁わ級** | **37.7s锛?.2脳锛?* | 11.8s锛圕PU 璺緞锛屾瘮鍘熷熀绾胯繕蹇級 | AV1 鍙洖 96.9%銆佽妫€ 0锛沨264 100% |
| 浠ｇ悊瑙嗛/浣庡抚鐜囷紙瀹為獙锛?| 鈮堜笉鍙彇 | 鈥?| 320px 闄嶉噰鏍蜂細璁?scene 闃堝€煎け鐪燂紙h264 300s锛?5鈫?77 璇锛汚V1 42min锛?96鈫?10 婕忔锛夛紝宸叉斁寮?|
| `-hwaccel cuda`锛堝疄楠岋級 | 涓庤蒋瑙ｆ寔骞?| 1.4脳 鎱?| 甯у洖鎷峰紑閿€鎶垫秷浜嗙‖瑙ｆ敹鐩?|
| `h264_cuvid` 纭В锛堝疄楠岋級 | 鈥?| 300s锛?5 鐪熷垏鐐硅妫€鎴?177 | **瑙ｇ爜鍍忕礌宸紓瀵艰嚧 scene 鍒嗘暟澶辩湡锛屽凡绂佺敤锛堜粎 av1 璧扮‖瑙ｏ級** |

宸ョ▼缁嗚妭锛?- 鍒嗗潡 `scene_chunk_s=300` + 0.5s 閲嶅彔 + 鍘婚噸锛涘垏鐐硅宸?鈮?.5s銆傚垎鍧椾篃瑙勯伩浜?AV1 闀胯繘绋嬪伓鍙戝穿婧冿細
  鏈瀹炴祴 1 涓潡锛?425s 璧凤級宕╂簝锛岃嚜鍔ㄥ鍗婃媶鍒嗗悗浠嶆湁鍧楀け璐?鈫?璇ュ潡鍥為€€杞В锛屽叏鐗囦粛鎴愬姛浜у嚭锛坄fallback_chunks` 浼氳褰曞湪 shots.json锛夈€?- 瑙嗛 1 h264 淇濇寔 CPU 鍗曡繘绋嬶紙11.8s 宸茶冻澶熷揩锛夛紱`scene_hw_codecs=["av1"]` 鍙湪 config 瑕嗙洊銆?- 鍦烘櫙+鏁呬簨鏉块噸寤猴細video 2 **57.5s**锛堝師 271.5s锛夛紝video 1 **22.1s**锛涙晠浜嬫澘 60 甯ч噸鎶?19.7s / 10.3s銆?- 浼樺寲鍚?video 2 鍏ㄧ储寮曢浼帮細涓嬭浇 60.6 + 闊抽 5.8 + ASR 103.4 + 鍦烘櫙 37.7 + 甯?19.7 鈮?**227s**锛堝師 443s锛夈€?- 椤哄甫淇 `read` 甯ф暟琛ラ綈锛氬皬绐楀彛鍐呮晠浜嬫澘甯т笌鍧囧寑閲囨牱鐐硅繃杩戜細琚烦杩囷紝瀵艰嚧璇锋眰 4 甯у彧鍥?3 甯э紱鐜颁繚璇併€岃姹傚灏戝抚灏卞洖澶氬皯甯с€嶃€?
### 4.2 M2-2锛氳瘝绾ф椂闂存埑 + 鍙ョ骇閲嶅垎娈碉紙娈电骇瀹氫綅绮惧害锛?
闂锛氬師 ASR 鍙瓨娈电骇鏃堕棿鎴筹紝video 2 鐨?253 娈甸噷鏈€闀夸竴娈?**386.4s**锛堥暱娈靛唴鍙湁 20 涓瘝鈥斺€斿ぇ閲忕幆澧冨０/闈欓煶琚苟杩涗竴娈碉級锛?璇煶鍐呭鍙兘瀹氫綅鍒般€岀獥鍙ｈ捣鐐广€嶏紝鏈€鍧忓亸宸彲杈炬暟鍒嗛挓銆?
鏂规锛歠aster-whisper `word_timestamps=True` 鍑鸿瘝绾ф椂闂达紙`words` 瀛樿繘 transcript.jsonl锛夛紝
鍐嶆寜 **ASR 鍘熷娈佃竟鐣?* + 鍙ユ湯鏍囩偣 / 璇嶉棿鍋滈】 鈮?.6s / 鏈€闀?12s 閲嶅垎娈碉紱`search` 鍛戒腑鏃剁敤璇嶇骇閿氱偣杩斿洖 `anchor`銆?
| 鎸囨爣 | video 2锛堣嫳鏂?42min锛?| video 1锛堜腑鏂?25min锛?|
|---|---|---|
| 鍘熷 ASR 娈?| 253 娈碉紝鏈€闀?**386.4s** | 728 娈碉紝鏈€闀?4.88s |
| 閲嶅垎娈靛悗 | **416 鍙ョ骇娈碉紝鏈€闀?9.18s** | **729 娈碉紝鏈€闀?4.88s** |
| 璇嶆暟 | 3,623 | 6,642锛堜腑鏂囧瓧绾э級 |
| 璇嶇骇鏃堕棿鎴冲紑閿€ | 鍚?120s 鍒囩墖 6.6s vs 6.9s锛堟棤鏄捐憲澧炲姞锛?| 鈥?|
| 閲嶈窇 ASR | **70.9s锛圧TF 0.026 鈮?37.8脳锛?* | **100.1s锛圧TF 0.064 鈮?15.7脳锛?* |

瀹氫綅绮惧害瀹炴祴锛坄search` 鐨?`anchor` 瀛楁锛夛細

| 鏌ヨ | 鏃ц緭鍑猴紙绐楀彛璧风偣锛?| 鏂拌緭鍑猴紙璇嶇骇閿氱偣锛?|
|---|---|---|
| `crossroads turn left` | 2359.17s锛堝亸 6s+锛屼笖绐楀彛娣峰叆涓婁笅鏂囷級 | **2365.61鈥?366.39s**锛坄crossroads` 璇嶈捣鐐癸級 |
| `hopper` | 1286.99s锛堟璧风偣锛?| **1287.23鈥?287.61s** |
| `纾侀搧`锛堜腑鏂囷級 | 176.8s 绐楀彛 | **229.84鈥?30.24s**锛堝懡涓瘝瀹為檯鏃堕棿锛?|

宸ョ▼缁嗚妭锛?- 閲嶅垎娈?*鎸夊師濮?ASR 娈佃竟鐣屽垏**锛氫腑鏂囧師濮嬫宸叉槸 ~2s 鐭绾э紝璺ㄦ鍚堝苟浼氶€€鍖栨垚 12s 澶у潡锛堟浘璇曡繃锛屼腑鏂?728 娈佃骞舵垚 121 娈碉紝宸蹭慨锛夈€?- 璇嶇骇鏁版嵁鍙敤浜庢绱㈤敋鐐癸細MCP 鐨?`read`/`transcript` 杈撳嚭浼氳鎺?`words`锛堥伩鍏嶄笂涓嬫枃鑶ㄨ儉锛夛紝瀛樺偍閲屼繚鐣欍€?- 闀挎鍐呮病鏈夎瘝鐨勬椂闂存锛堢函鐜澹帮級涓嶄細琚吉閫犳枃鏈紝閲嶅垎娈靛悗鑷劧鐣欑櫧銆?
## 4.3 M2-3锛氬悎闆?鍒哖 姒傝 + p2锛?h锛夊叏閾捐矾瀹炴祴锛?026-10-30 杩藉姞锛?
鏂板 `collection` 姒傝锛圡CP 宸ュ叿 + CLI锛夛細鍒楀嚭鍚堥泦鎵€鏈夊垎P鐨勬爣棰?鏃堕暱/绱㈠紩鐘舵€侊紝宸茬储寮曞垎P闄勭珷鑺傜洰褰曚笌鍏抽敭璇嶃€?鍚屾椂淇浜嗗垎P涓嬭浇鐨勪竴涓湡瀹?bug锛歚--playlist-items N` 涓?`--no-playlist` 鍚岀敤鏃?yt-dlp 浼氬拷鐣ュ垎P閫夋嫨锛?瀵艰嚧 p2 瀹為檯涓嬭浇鎴?p1锛坉uration 2509s锛夈€傛敼涓?`?p=N` URL 鍚庯紝p2 姝ｇ‘涓嬭浇涓?7354s銆?
p2锛坄Bilibili BV17q9EBEE9w p02`锛岃嫳鏂?122.6min锛夊疄娴嬶細

| 姝ラ | 瀹炴祴 | 澶囨敞 |
|---|---|---|
| 涓嬭浇 720p 瑙嗛+闊抽 | **246.8s / 322MB** | 240.35MiB 瑙嗛 + 82.03MiB 闊抽锛涙湰娆＄綉缁滀粎 ~1.1MiB/s |
| 闊抽鎶藉彇 16k | 5.6s | |
| **ASR** | **184.7s锛圧TF 0.0244 鈮?41脳锛?* | 737 鍘熷娈?鈫?閲嶅垎娈?**1084 娈?*锛?,688 璇嶏紱en |
| 鍦烘櫙鍒囧垎锛圕UVID 鍒嗗潡锛?| **83.0s / 405 闀滃ご** | 25 涓垎鍧楋紝鏃犺蒋瑙ｅ洖閫€锛涘钩鍧囬暅澶?18.2s銆佷腑浣?4.5s |
| 鏁呬簨鏉?60 甯?| 19.5s | |
| **绱㈠紩鎬昏€楁椂** | **540.6s 鈮?9.0min** | 2h 瑙嗛锛涙棤瀛楀箷銆佸叏鑷姩 |
| 鍚堥泦姒傝 | p1 10 鑺?+ p2 12 鑺?| 鎬绘椂闀?9,864s锛?h44m24s锛夛紝2/2 宸茬储寮?|
| p2 璇嶇骇瀹氫綅 | `crossroads`鈫?86.2s銆乣library`鈫?208.7s銆乣the king`鈫?553.0s | anchor 涓庣敾闈?瀛楀箷涓€鑷?|

缂撳瓨鍗犵敤锛? 涓潯鐩級锛?*513MB**銆俙collection` 宸查€氳繃 DSH MCP 瀹炴祴锛坄mcp__video__collection` 杩斿洖 2 椤点€?/2 宸茬储寮曪級銆?
### 4.4 M2-4锛歜vid 褰掍竴 + 10GB LRU锛?026-10-30 杩藉姞锛?
**褰掍竴鍓?*锛氬悓涓€瑙嗛鍦ㄧ紦瀛橀噷鏈?3 鏉¤褰?鈥斺€?`local_bf0bd08779c206a3`锛?2.2MB锛孉SR 绱㈠紩锛夈€?`local_436062500ba7ed43`锛?1.3MB锛屽唴宓屽瓧骞曠储寮曪級銆乣bili_BV1xrnz6gEVD`锛?MB锛屼粎 URL 鍏冩暟鎹級銆?
**褰掍竴鍚?*锛坄vidx.cli cache --migrate --apply`锛夛細

| 椤?| 缁撴灉 |
|---|---|
| canonical id | `bili_BV1xrnz6gEVD`锛坆vid 浼樺厛锛?|
| 缂撳瓨鏉＄洰 | 5 鈫?**3**锛堥噸澶嶅悎骞?1 缁勶紝2 涓埆鍚嶏級 |
| 绱㈠紩澶嶇敤 | 淇濈暀 `local_bf` 鐨?ASR 绱㈠紩锛?29 娈?/ 6642 瀛?/ 60 甯э級 |
| 鏃?id | `local_bf...` / `local_436...` 缁х画鍙敤锛坅liases.json锛?|
| 鍘熺洰褰?| 绉诲叆 `.trash/20261030-231133`锛?3.5MB锛屽彲鎵嬪姩娓咃級 |
| `open(鏈湴 mp4)` | 鈫?`bili_BV1xrnz6gEVD`锛宺eady锛?*0.08s** |
| `open(URL)` | 鈫?鍚屼竴 id锛宺eady锛?.69s锛堝厓鏁版嵁鍒锋柊锛屼笉閲嶅涓嬭浇/ASR锛?|
| 浜屾 `index(鏈湴)` | **0.16s**锛堜笉 ASR锛屽満鏅储寮曠洿鎺ュ鐢級 |
| 浜屾 `index(URL)` | **0.75s**锛宍timings.media_reused=1`锛堝悓 bvid 鏈湴鍓湰锛岃烦杩囦笅杞斤級 |
| 濯掍綋澶嶇敤鏍￠獙 | 鍚?bvid + 鍚?page + 鏂囦欢瀛樺湪 + 鏃堕暱宸?鈮?s |
| 鏃?id 璋冪敤 | `status/outline/search("local_bf...")` 鍏ㄩ儴姝ｅ父锛堣В鏋愬埌 canonical锛?|

**10GB LRU**锛歚vidx.cli cache --prune`锛堥粯璁?dry-run锛屽彧鍑烘竻鍗曪級鈫?`--apply` 鎵嶅垹锛?鎸?`last_used` 浠庢棫鍒版柊娣樻卑**鏁翠釜瑙嗛鐩綍**锛宍.trash/` 瑙嗕负鏈€鏃у厛娓咃紱鏀寔 `--cap-gb` 瑕嗙洊銆乣pinned=true` 淇濇姢銆?瀹炴祴锛歚--prune --cap-gb 1 --apply` 鏃犺秴闄?鈫?涓嶅垹浠讳綍涓滆タ锛沗--prune --cap-gb 0.5 --apply` 鍙竻 `.trash`锛?3.5MB锛夈€?鍒犻櫎鍙綔鐢ㄤ簬缂撳瓨鐩綍锛?*涓嶄細纰扮敤鎴风殑鍘熷瑙嗛鏂囦欢**銆?
### 4.5 M2-5锛氬脊骞曞紑鍏筹紙榛樿鍏筹紝鎸夐渶鎶撳彇锛?
鐜扮姸锛氬脊骞曚唬鐮佹棭灏辨湁锛屼絾鎺ュ彛杩斿洖 **raw deflate**锛坄Content-Encoding: deflate` 鍗存病鏈?zlib 澶达級锛?鏃у疄鐜扮洿鎺ユ妸浜岃繘鍒朵涪缁?XML 瑙ｆ瀽 鈫?姘歌繙 0 鏉°€傚凡淇锛歚zlib.decompress(raw, -zlib.MAX_WBITS)`锛?骞跺湪 `_headers` 涔嬪鍏煎 api/comment 涓や釜鍩熷悕銆?
| 椤?| 瀹炴祴 |
|---|---|
| 寮€鍏?| **榛樿鍏抽棴**锛沗index(danmaku=true)` / CLI `index --danmaku` / `config.danmaku_default=true` 涓夐€変竴 |
| 鎶撳彇锛堝尶鍚嶏紝鏃犻渶鐧诲綍锛?| p1 **737 鏉?/ 0.35s / 63KB**锛沺2 **1,611 鏉?/ 0.29s / 135KB**锛汢V1xrnz6gEVD **3,600 鏉?/ 0.33s / 232KB** |
| 瀛樺偍 | `danmaku.jsonl`锛坄t/mode/color/text`锛夛紝鍗曟潯 ~80鈥?0B锛屽缂撳瓨鍑犱箮鏃犳劅 |
| 鏂板伐鍏?| MCP 绗?9 涓伐鍏?`danmaku(video_id, t0?, t1?, k?, refresh?)`锛汣LI `vidx.cli danmaku <id> [--fetch] [--from] [--to] [--limit]` |
| 鍖洪棿瀵嗗害绀轰緥 | p1 `02:56鈥?3:25`锛堢閾佹锛夛細8 鏉★紝**16.6 鏉?鍒嗛挓**锛岃繑鍥為噰鏍峰脊骞曪紙鈥滄敞鎰忥紝鐜板湪璇寸殑鍋囪閮戒笉瀵光€濃€滃湪鐨勫湪鐨勨€濃€︼級 |
| 骞傜瓑 | 宸叉湁 `danmaku.jsonl` 鏃?`ensure_danmaku` 鐩存帴杩斿洖锛坈ached=true锛夛紝涓嶉噸澶嶈姹?|

鐢ㄩ€旓細瑙嗛鎬荤粨涔嬪锛屽洖绛斺€滆繖娈佃浼椾粈涔堝弽搴?鍝噷楂樿兘鈥濆彲浠ョ洿鎺ョ粰寮瑰箷瀵嗗害 + 閲囨牱锛涗篃鍙互鍜?`outline/read` 鐨勬椂闂存埑瀵归綈銆?
### 4.6 M3锛氬彸渚ф爮銆岃棰戞椂闂磋酱銆嶉潰鏉匡紙v1锛?
鏂板 `video-plugin/dsh-video-panel`锛坔ost + client 涓ゅ崐锛屾墜鍐?ESM/CJS锛屾棤鏋勫缓姝ラ锛夛細

| 椤?| 缁撴灉 |
|---|---|
| host 鏁版嵁鎺ュ彛 | `/video-panel/api?action=list/detail/read/search/danmaku` + `/video-panel/frame`锛堝彧鍏佽 `_video_cache` 涓?PNG锛夊叏閮ㄥ疄娴?200 |
| 鏁版嵁鏉ユ簮 | `python -m vidx.panel_api`锛坋ngine 鐨?pipeline锛氳瘝绾?anchor銆侀噸鍒嗘銆佸脊骞曢兘澶嶇敤锛屼笉鍦?Node 閲嶅瀹炵幇锛?|
| 瀹炴祴 | list=3 涓棰?492MB锛沝etail锛坕Phone 璇勬祴锛塻ections=5銆乫rames=60锛況ead 220鈥?60s 鈫?25 娈?+ 3 甯э紱frame 200/291KB |
| client 娉ㄥ唽 | `sidebarRightTabs` 娉ㄥ唽 `dsh-video-timeline`锛坓uide 鍏ュ彛銆岃棰戞椂闂磋酱銆嶏級锛沚ody/title 娉ㄥ唽鍒?`sidebar.right.pane.tab`/`.title`锛坘ey=鎻掍欢 id锛夆€斺€擭ode 娌欑妯℃嫙娉ㄥ唽搴忓垪閫氳繃 |
| 闈㈡澘鍐呭 | 瑙嗛涓嬫媺銆佺珷鑺?鍏抽敭甯у埢鐐规椂闂磋酱锛堢偣鍑昏烦杞?绾㈢嚎鎸囩ず锛夈€佸墠鍚?15s 瀛楀箷+4 甯у浘銆佸叧閿瘝妫€绱紙璇嶇骇 anchor 璺宠浆锛夈€佸鍒跺紩鐢?|
| 鐢熸晥鏂瑰紡 | host 宸茬儹娉ㄥ叆锛?*client 闇€鍒锋柊椤甸潰涓€娆?*锛坆undle 鍦ㄩ〉闈㈠姞杞芥椂娉ㄥ唽锛夛紝鍒锋柊鍚庯細鍙充晶鏍?`+` 鈫?鎸囧崡 鈫?銆岃棰戞椂闂磋酱銆?|
| v1.1 鐐瑰嚮鎻愰棶 | host `action=ask`锛圥OST `{session_id,text}`锛夆啋 `ctx.agents.get(id).followup(createUserMessage(...))`锛沵ock 鍗曟祴閫氳繃锛?00 + 娑堟伅 shape `{role:'user', content:[text], id:uuid}`锛夛紱client銆岀偣鍑诲嵆鎻愰棶銆嶅嬀閫?銆岄棶 agent銆嶆寜閽妸鍓嶅悗 15s 鎻愮ず鍙戣繘褰撳墠浼氳瘽 |
| v1.1 瑙嗛娓呯悊 | 涓嬫媺姣忛」 `脳`锛坄action=delete`锛?銆屾竻绌哄叏閮ㄧ紦瀛樸€嶏紙`action=clear`锛夛紱鍒犻櫎鍙姩 `_video_cache`锛屼笉纰板師濮嬫枃浠讹紱鍒犻櫎 dummy 鐩綍瀹炴祴鎴愬姛銆佷笉瀛樺湪鏃惰繑鍥為敊璇?|
| 绌虹姸鎬?| 涓嶅啀鑷姩閫変腑瑙嗛锛氭病鏈夎棰戦渶姹傛椂闈㈡澘绌虹櫧锛屼笉琚姩灞曠ず缂撳瓨閲岀殑娴嬭瘯瑙嗛 |
| 宸茬煡鍧?| **瀵?`@local/dsh-video-panel` 鎵ц `dev_reload_package` 浼氬崱浣?DSH锛堥渶寮哄埗閲嶅惎锛?*锛沨ost 鏀瑰姩璇烽噸鍚?DSH锛宑lient 鏀瑰姩鍒锋柊椤甸潰 |

璇存槑锛歚dev_inject_plugin` 鐨勯潤鎬佹牎楠屽彧璁ゅ浐瀹?slot 鐧藉悕鍗曪紙涓嶅惈 `sidebar.right.pane.tab`锛夛紝client 鏂囦欢閲屼繚鐣欎簡涓€琛屾敞閲婂崰浣嶄互閫氳繃鏍￠獙锛涘疄闄呮敞鍐屼粛鏄彸渚ф爮 keyed slot銆?`dev_install_package` 宸叉妸鏈寘鍐欏叆 profile dependencies+bundles锛岄噸鍚悗鐢?bundle patch 鑷姩瑁呴厤锛坄cordis.patch.yml`锛夈€?



## 5. MCP / DSH 闆嗘垚楠岃瘉锛圡1/M2锛?
| 妫€鏌?| 缁撴灉 |
|---|---|
| `dsh-video` bundle 鐑閰?| 鉁?`dev_install_package`锛坧rofile dependencies+bundles+link+loader.create锛?|
| MCP 宸ュ叿娉ㄥ唽 | 鉁?9 涓細`open/index/status/outline/read/search/transcript/collection/danmaku` |
| 寮瑰箷寮€鍏筹紙M2-5锛?| 鉁?榛樿鍏筹紱`danmaku(refresh=true)` 鎶撳彇鍚?query锛涘疄娴?p1 737 / p2 1611 / 鍗曢泦 3600 鏉?|
| **bvid 褰掍竴锛圡2-4锛?* | 鉁?`open(鏈湴 mp4)` 涓?`open(URL)` 杩斿洖鍚屼竴 `video_id=bili_BV1xrnz6gEVD`锛涙棫 `local_*` id 缁?alias 缁х画鍙敤 |
| `open`锛堟湰鍦?+ bilibili URL锛?| 鉁?鍏冩暟鎹?鍒哖/绔犺妭/瀛楀箷鐘舵€?绱㈠紩鐘舵€侊紱BV 瑙嗛鍖垮悕 `subtitle_tracks: []` |
| `index` 鈫?`status(wait_s)` | 鉁?绔嬪嵆杩斿洖 task_id锛涢暱杞鏈?stage/pct/鏈€杩戞棩蹇楋紱瀹屾垚鍚庡甫 result |
| `outline` | 鉁?骞冲彴绔犺妭锛坴ideo1锛? 鑷姩鍒嗘锛坴ideo2锛?|
| **`read` 杩斿洖鍥剧墖** | 鉁?DSH 灏?MCP `image` block 鎶曞奖杩涘璇濓紝涓绘ā鍨嬪彲鐩存帴鐪嬪浘骞舵嵁姝ゅ洖绛?|
| `search` | 鉁?涓嫳鏂?bigram + 鏈€杩戝叧閿抚 |
| `transcript` | 鉁?鍏ㄦ枃/鍖洪棿锛堢敤浜庢暣鐗囨€荤粨锛?|
| 鎻掍欢鐑噸杞?| 鉁?`dev_reload_package dsh-video` 鍚庡伐鍏蜂粛姝ｅ父锛圡CP server 閲嶅惎锛?|

## 6. 宸茬煡闂 / 寰呭姙

1. ASR 閫熷害鍙?GPU 鐢垫簮鐘舵€佸奖鍝嶅ぇ锛?脳鈥?2脳锛夛紱寤鸿杩愯鍓嶆彃鐢?楂樻€ц兘妯″紡锛屽苟鍦ㄦ棩蹇楁彁绀恒€?2. ~~`open` 鍚屼竴瑙嗛鐨?URL 涓庢湰鍦版枃浠朵細寰楀埌涓や釜 video_id锛坄bili_*` / `local_*`锛夛紝绱㈠紩涓嶅叡浜珇~
   **宸插湪 M2-4 瑙ｅ喅**锛氭湰鍦版枃浠舵寜 sidecar bvid 褰掍竴锛坄bili_BV1xrnz6gEVD`锛夛紝鍒悕琛ㄥ吋瀹规棫 id锛?   鎵撳紑 URL 鏃惰嫢缂撳瓨鏈夊悓 bvid 鏈湴鍓湰鍒欑洿鎺ュ鐢ㄥ獟浣擄紙`media_reused=1`锛夈€?3. ~~鍦烘櫙妫€娴嬫槸闀胯棰戜富瑕佺摱棰垀~ **宸插湪 M2-1 瑙ｅ喅**锛圓V1 42min 233鈫?7.7s锛夛紱鍓╀綑鐡堕鏄笅杞戒笌 ASR锛堣棰?2 鍚堣 ~160s锛夈€?   鏋佸皯鏁板潡鍙兘瑙﹀彂 AV1 纭В宕╂簝 鈫?宸插疄鐜拌嚜鍔ㄦ媶鍧?杞В鍥為€€銆?4. `read` 鍗曟鍥剧墖 鈮?銆佸 960px锛涜秴鍑虹敱 DSH image-offload 绠＄悊銆?5. 寮瑰箷宸插疄鐜帮紙M2-5锛岄粯璁ゅ叧闂紝瑙?搂4.5锛涢渶瑕佹椂 `index(danmaku=true)` 鎴?`danmaku(refresh=true)`锛夛紱
   OCR 灞忓箷鏂囧瓧绱㈠紩/鏈湴 VLM 鍧囨湭鎺ュ叆锛堟寜褰撳墠鏂规涓嶉渶瑕侊級銆?6. 鍦烘櫙妫€娴?鏁呬簨鏉垮皻鏈笌 ASR 骞惰锛堝彲鍐嶇渷 1鈥?min锛夈€?7. video 1 鐢ㄦ埛绉扳€滄湁瀛楀箷鈥濓紝瀹為檯鏄?*鐢婚潰鐑у綍鐨勭‖瀛楀箷**锛堜緥濡?08:11 涓€甯у彲瑙佲€滀粬浠兘璇磋兘浠庡彛琚嬮噷鈥濓級锛?   鍖垮悕鎺ュ彛娌℃湁 CC/AI 瀛楀箷杞紙`subtitle_tracks=[]`锛屽彧鏈?5 涓钩鍙扮珷鑺傦級銆傚綋鍓?ASR 宸茶鐩栬闊虫枃鏈紝
   纭瓧骞曞彲鐢变富妯″瀷瑙嗚鐩存帴璇伙紱鑻ヨ CC/AI 瀛楀箷 + 骞冲彴 AI 澶х翰锛岄渶瑕佸彲閫?SESSDATA銆?8. 鍚堥泦/鍒哖 鐨勮法闆嗘瑙堛€乁I 鏃堕棿杞撮潰鏉裤€佺瑪璁板鍑猴紙md/docx锛夊皻鏈疄鐜帮紙M2/M3锛夈€?
## 闄勫綍 A锛氫腑鏂?ASR 鏍蜂緥锛坴ideo 1锛?
> 鏃㈢劧鏄姌鍙犲睆骞曢棶棰?鈥?iPhone Duo 鍥犱负瀹冩姌鍙犵殑褰㈡€?浼氬鑷翠綘鎵撳瓧杩樻湁鎵撶數璇濈殑鏂瑰紡 閮戒骇鐢熶竴浜涘彉鍖?鈥?> 閭ｅ儚鎵撳瓧浣犳湁绔栫潃鎵?妯潃鎵?鍗婃姌鍙犳墦 鍏ㄦ姌鍙犳墦 杩欎箞澶氱鎵撴硶 閭ｈ繖鍥涚鎵撴硶閲岄潰 鎴戜滑鐩墠鐪嬩笅鏉ユ渶蹇渶鍑嗙殑
> 鍏跺疄鏄珫鐫€鎵?鍗婃姌鐨勫舰鎬佹槸鏈€鎱㈢殑 鈥?杩欎釜 Duo 鐨勯煶璐ㄦ槸姣?18 Pro 寮辩殑 浣嗘槸瀹冨湪鍚勪釜褰㈡€佷箣涓嬬殑澹伴煶鍧囪　
> 鎴戣寰楀仛鐨勯潪甯镐笉閿?鈥?iPhone 18 Pro 鍜?Duo 鐨?MagSafe 纾佺幆閮芥槸鏂帀鐨?鑰屼笖鏂殑浣嶇疆鏄笉涓€鏍风殑 鈥?> 鑰屼笖 Duo 涓ぎ鏈夎繖涔堜竴棰楅潪甯哥嫭鐗圭殑纾侀搧 鈥?浣嗘槸鍒颁粖澶╂垜浠粛鐒朵笉纭畾杩欎釜纾侀搧鍏蜂綋鐨勪綔鐢ㄦ槸浠€涔?
## 闄勫綍 B锛氳嫳鏂?ASR 鏍蜂緥锛坴ideo 2 p1锛?
> Whatever you do at the crossroads, don't turn left鈥︼紙鍙嶅鍑虹幇锛屾槸瑙嗛鐨勬牳蹇冭皽棰橈級
> Opening the video named Footage 1鈥?Avery explains in the description that the laptop he's playing on
> is from a storage locker鈥?the numbers at the end are clearly some sort of code鈥?> dead end after dead end, Avery navigates through it. Avery is clearly smart鈥?> But whatever this thing is that's following him, it's smart too鈥?Smart enough to hide its presence.

## 闄勫綍 C锛氬鐜板懡浠?
```powershell
$PY = '<repo>\.venv\Scripts\python.exe'
cd <workspace>\video-plugin\engine
& $PY -m vidx.cli selftest
& $PY -m vidx.cli open  '...\video-plugin\testdata\iphone_duo.mp4'
& $PY -m vidx.cli index '...\video-plugin\testdata\iphone_duo.mp4'
& $PY -m vidx.cli index '...\video-plugin\testdata\iphone_duo_subs.mkv'   # 瀛楀箷浼樺厛锛?2s锛?& $PY -m vidx.cli outline local_bf0bd08779c206a3
& $PY -m vidx.cli read    local_bf0bd08779c206a3 176 205 --frames 3
& $PY -m vidx.cli search  local_bf0bd08779c206a3 "纾侀搧"
& $PY tests/mcp_smoke.py
```

