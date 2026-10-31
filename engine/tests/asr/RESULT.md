# vidx ASR 妯″潡鑷祴缁撴灉锛圧ESULT.md锛岃嚜鍔ㄧ敓鎴愶級

- 鐢熸垚鏃堕棿锛?026-10-30 21:22:28銆€鑰楁椂锛?89.84s銆€缁撹锛?*鍏ㄩ儴 PASS**
> **璐熷鐓э紙T9 nodll锛夎鏄?*锛氭鍓嶄竴鐗?RESULT.md 鏈?3 涓?nodll FAIL锛屾槸**娴嬭瘯鑴氭墜鏋堕棶棰?*鈥斺€旂埗杩涚▼娉ㄥ唽 DLL 鏃舵妸 nvidia 鐩綍鍐欒繘 PATH锛屽瓙杩涚▼缁ф壙鍚庝粛鑳借В鏋愬埌 cublas锛屾瀯閫犱笉鍑哄け璐ュ満鏅紱**涓嶆槸妯″潡缂洪櫡**銆傜幇宸蹭慨姝ｏ細瀛愯繘绋?PATH 鍓旈櫎 nvidia 鐩綍鍚庤礋瀵圭収鎴愬姛澶嶇幇骞?PASS锛坈types 棰勬鍙戠幇 cublas 缂哄け 鈫?璺宠繃 2 涓?cuda 鍊欓€?鈫?19.3s 鍥為€€ cpu/int8锛?*鏃犲崱姝?*锛夈€俙register_cuda_dlls()` 瀹炴祴娉ㄥ唽 3 涓洰褰曪紙瑙佷笅锛夈€?>
> **鑰楁椂璇存槑**锛氭湰琛ㄤ负鏈€鍚庝竴娆″叏閲忚繍琛岋紙鏈熼棿鏈夊叾瀹冭繘绋嬪崰鐢?GPU 66鈥?00%锛屽睘鍋忔偛瑙傚€硷級銆侴PU 绌洪棽鏃剁殑瀵圭収瀹炴祴锛氳嫳璇?120s **6.08s锛?9.7x 瀹炴椂锛?*銆佷腑鏂囩湡瀹?120s **9.74s锛?2.3x锛?*銆佹ā鍨嬪姞杞?**7.1s**锛坈tor 6.3s + probe 0.8s锛夛紱GPU 鍏辩害 19.7x锛孋PU int8 绾?3.5x锛坱ask-1 鍩哄噯锛夈€?>

- Python 3.10.6（<repo>/.venv），faster-whisper / CTranslate2（无 torch）
- faster-whisper 1.2.1 / CTranslate2 4.8.2 / numpy 2.2.6 / torch 鏈娇鐢?
- GPU锛歂VIDIA GeForce RTX 3050 Ti Laptop GPU锛?096 MiB锛宒river 592.82锛涙祴璇曞墠宸茬敤 0 MiB锛孏PU util 0%锛堣嫢鏈夊叾瀹冭繘绋嬪崰鐢?GPU锛屾湰琛ㄨ€楁椂浼氬亸澶э級
- CUDA DLL 娉ㄥ唽鐩綍锛? 涓紝import 鍓嶆敞鍐岋級锛?
  - `<repo>\.venv\Lib\site-packages\nvidia\cublas\bin`
  - `<repo>\.venv\Lib\site-packages\nvidia\cuda_nvrtc\bin`
  - `<repo>\.venv\Lib\site-packages\nvidia\cudnn\bin`
- ctranslate2.get_cuda_device_count() = 1锛堟敞鎰忥細**涓嶈兘**鐢ㄥ畠鍒ゆ柇GPU 鍙敤鎬э紝瑙?搂4锛?

## 1. health()
璋冪敤鑰楁椂 17.11s锛堝惈鍐峰姞杞?+ 1s 闈欓煶鐪熷疄鎺ㄧ悊 probe锛夛細
```json
{
  "ok": true,
  "device": "cuda",
  "compute_type": "int8_float16",
  "model": "faster-whisper-large-v3-turbo",
  "load_s": 16.906,
  "load_breakdown": {
    "ctor_s": 14.953,
    "probe_s": 1.953
  },
  "idle_s": 0.0,
  "error": null,
  "model_dir": "<repo>/models/faster-whisper-large-v3-turbo",
  "language": null,
  "loaded": true,
  "loads": 1,
  "unloads": 0,
  "idle_unloads": 0,
  "idle_unload_s": 600.0,
  "last_unload_reason": null,
  "attempts": [],
  "cuda_dlls_ok": true,
  "cuda_dlls_error": null
}
```

## 2. 杞啓瀹炴祴

| 鐢ㄤ緥 | 闊抽 | 璇█ | device/compute | 鏃堕暱s | load_s | wall_s | RTF | 瀹炴椂鍊嶉€?| 娈垫暟 | 瀛楃 |
|---|---|---|---|---|---|---|---|---|---|---|
| 鑻辫鐪熷疄浜哄０ 120s | en_120s.wav | en (p=1.0) | cuda/int8_float16 | 120.0 | 16.906 | 14.797 | 0.1233 | 8.11x | 34 | 1687 |
| 涓枃 TTS 13s锛堣嚜鍔ㄦ娴嬶級 | zh_tts_16k.wav | zh (p=0.998) | cuda/int8_float16 | 13.0 | 16.906 | 3.875 | 0.2981 | 3.35x | 4 | 47 |
| 涓枃鐪熷疄浜哄０ 120s锛堣嚜鍔ㄦ娴嬶級 | zh_real_120s.wav | zh (p=0.9985) | cuda/int8_float16 | 120.0 | 16.906 | 23.672 | 0.1973 | 5.07x | 64 | 859 |
| CPU-only 鍥為€€锛堜腑鏂?TTS锛?| zh_tts_16k.wav | zh (p=0.9981) | cpu/int8 | 13.0 | 17.469 | 26.312 | 2.024 | 0.49x | 4 | 47 |
| transcribe_file 涓€娆℃€э紙涓枃 TTS锛?| zh_tts_16k.wav | zh (p=0.998) | cuda/int8_float16 | 13.0 | 9.344 | 3.828 | 0.2945 | 3.4x | 4 | 47 |

鑻辫 120s 棣栨鏂囨湰锛歠rom your land. You can't shoot badgers and keep them away from your land. They're a protected

## 3. 鍗歌浇 / 閲嶈浇 / 绌洪棽鍗歌浇
- `unload()` 鑰楁椂 0.04s锛涙樉瀛?1187 鈫?99 MiB锛堥噴鏀?~1088 MiB锛?
- unload 鍚?`loaded=False`锛沗health()` 瑙﹀彂閲嶈浇鑰楁椂 **8.39s**锛坙oad_s=8.375锛宭oads=2锛?
- 绌洪棽鍗歌浇锛坕dle_unload_s=2锛岀潯鐪?2.3s 鍚?health()锛夛細idle_unloads 0 鈫?1锛宭ast_reason=idle锛岄噸杞借€楁椂 10.22s锛岄噸杞藉悗 ok=True

## 4. 鍥為€€閾捐瘉鎹?

**璐熷鐓э細璁剧疆 `VIDX_ASR_NO_DLL_REGISTER=1`锛堜笉娉ㄥ唽 nvidia DLL锛夊苟浠庡瓙杩涚▼ PATH 涓墧闄?nvidia 鐩綍锛宍device=auto`銆?* 瀛愯繘绋?rc=0锛岃€楁椂 19.3s锛岃秴鏃?False锛宑uda_dll_dirs=[]銆傦紙瀹炴祴鍙戠幇锛氱己 DLL 鏃剁 1 涓?cuda 鍊欓€夊揩閫熸姤 cublas 閿欒锛?*绗?2 涓?cuda 鍊欓€変細鍦?encode 姘镐箙鍗℃**锛沘sr.py 鍥犳鍔犱簡 ctypes 棰勬 + 鍒濆鍖栫被澶辫触鍗宠烦杩囧叾浣?cuda 鍊欓€?+ probe 瓒呮椂瀹堟姢銆傦級
```json
{
  "ok": true,
  "device": "cpu",
  "compute_type": "int8",
  "model": "faster-whisper-large-v3-turbo",
  "load_s": 18.281,
  "load_breakdown": {
    "ctor_s": 7.062,
    "probe_s": 11.219
  },
  "idle_s": 0.0,
  "error": null,
  "model_dir": "<repo>/models/faster-whisper-large-v3-turbo",
  "language": null,
  "loaded": true,
  "loads": 1,
  "unloads": 0,
  "idle_unloads": 0,
  "idle_unload_s": 600.0,
  "last_unload_reason": null,
  "attempts": [
    {
      "device": "cuda",
      "compute_type": "int8_float16",
      "error": "璺宠繃锛圕UDA DLL 棰勬澶辫触锛? cublas64_12.dll: Could not find module 'cublas64_12.dll' (or one of its dependencies). Try using the full path with constructor syntax."
    },
    {
      "device": "cuda",
      "compute_type": "float16",
      "error": "璺宠繃锛圕UDA DLL 棰勬澶辫触锛? cublas64_12.dll: Could not find module 'cublas64_12.dll' (or one of its dependencies). Try using the full path with constructor syntax."
    }
  ],
  "cuda_dlls_ok": false,
  "cuda_dlls_error": "cublas64_12.dll: Could not find module 'cublas64_12.dll' (or one of its dependencies). Try using the full path with constructor syntax."
}
```
**鍧忔ā鍨嬬洰褰?*锛歨ealth.ok=False锛宔rror=`ASR 妯″瀷鐩綍涓嶅瓨鍦? '<home>/…'`锛泃ranscribe 鎶?ASRError=True

## 5. CLI锛坧ython -m vidx.asr锛屼粠 engine/ 杩愯锛?
- 杞啓锛歳c=0锛?0.94s锛孞SON 鍐欏嚭=True锛宻egments=4锛宺tf=0.1959
- `--health`锛歳c=0锛坰tdout 鍓?200 瀛楋級`{
  "ok": true,
  "device": "cuda",
  "compute_type": "int8_float16",
  "model": "faster-whisper-large-v3-turbo",
  "load_s": 7.547,
  "load_breakdown": {
    "ctor_s": 5.734,
    "probe_s": 1.813
  }`

## 6. PASS/FAIL 鏄庣粏

| # | 妫€鏌?| 缁撴灉 | 璇︽儏 |
|---|---|---|---|
| 1 | assets.zh_tts_exists | PASS | <workspace>\_plan_video_plugin\asr\zh_tts_16k.wav |
| 2 | health.ok | PASS |  |
| 3 | health.device | PASS | cuda |
| 4 | health.compute_type | PASS | int8_float16 |
| 5 | health.model_large | PASS | faster-whisper-large-v3-turbo |
| 6 | health.load_s_positive | PASS | 16.906 |
| 7 | en.keys | PASS |  |
| 8 | en.segments_nonempty | PASS | 34 segs |
| 9 | en.timestamps_monotonic | PASS |  |
| 10 | en.duration_120 | PASS | 120.0 |
| 11 | en.language_en | PASS |  |
| 12 | en.progress_called_per_segment | PASS | 34 calls / 34 segs |
| 13 | en.rtf_faster_than_realtime | PASS | 0.1233 |
| 14 | en.text_len | PASS | 1687 |
| 15 | en.device_cuda | PASS |  |
| 16 | zh_tts.auto_detect_zh | PASS | lang=zh p=0.998 |
| 17 | zh_tts.language_forced_none | PASS |  |
| 18 | zh_tts.text_has_zh | PASS | 杩欐槸涓€涓腑鏂囪闊宠瘑鍒祴璇?浠婂ぉ澶╂皵寰堝ソ 鎴戜滑涓嬪崍涓€璧峰幓鍏洯鏁ｆ 瑙嗛闃呰鎻掍欢闇€瑕佹妸闊抽杞垚鏂囧瓧 |
| 19 | zh_tts.language_prob | PASS | 0.998 |
| 20 | zh_real.auto_detect_zh | PASS | lang=zh p=0.9985 |
| 21 | zh_real.rtf | PASS | 0.1973 |
| 22 | zh_real.segments | PASS | 64 |
| 23 | zh_real.text_has_zh | PASS | Pro鍓╀笅87 鑰孌uo杩欐椂鍊欏彧鏈?4%浜?鎵€浠uo鐨勮€楃數鍜屽畠杩欎釜灞忓箷鐨勫埄鐢ㄧ巼 鏈夊緢澶х殑鍏崇郴 涓€鏃﹀睆骞曞埄鐢ㄧ巼鎻愰珮 鐢甸噺 |
| 24 | unload.loaded_false | PASS |  |
| 25 | unload.vram_released | PASS | 1187 鈫?99 MiB |
| 26 | unload.reload_ok | PASS | reload 8.39s |
| 27 | unload.reload_counter | PASS | 2 |
| 28 | idle.unload_triggered | PASS | 1 |
| 29 | idle.reloaaded_ok | PASS |  |
| 30 | idle.last_reason | PASS | idle |
| 31 | cpu.health_ok | PASS |  |
| 32 | cpu.transcribe_ok | PASS |  |
| 33 | bad_model.health_not_ok | PASS | ASR 妯″瀷鐩綍涓嶅瓨鍦? '<home>/…' |
| 34 | bad_model.error_mentions_dir | PASS |  |
| 35 | bad_model.transcribe_raises | PASS |  |
| 36 | nodll.child_finished | PASS | rc=0 wall=19.3s |
| 37 | nodll.preflight_detects_missing_dll | PASS | cublas64_12.dll: Could not find module 'cublas64_12.dll' (or one of its dependencies). Try using the full path with constructor syntax. |
| 38 | nodll.health_ok_on_cpu | PASS | cpu/int8 |
| 39 | nodll.cuda_attempts_skipped | PASS | ['cuda', 'cuda'] |
| 40 | nodll.error_is_cublas | PASS | {'device': 'cuda', 'compute_type': 'float16', 'error': "璺宠繃锛圕UDA DLL 棰勬澶辫触锛? cublas64_12.dll: Could not find module 'cublas64_12.dll' (or one of its dependencies). Try using the full |
| 41 | nodll.no_dll_dirs | PASS |  |
| 42 | cli.transcribe_rc0 | PASS | 0 |
| 43 | cli.json_written | PASS |  |
| 44 | cli.json_has_segments | PASS | 4 |
| 45 | cli.health_rc0 | PASS | 0 |
| 46 | one_shot.keys | PASS |  |
| 47 | one_shot.language_zh | PASS | zh |

## 7. 澶囨敞 / 鏈獙璇侀」

- 鑻辫涓庝腑鏂?TTS 杞啓鍧囧凡楠岃瘉锛涗腑鏂?*鐪熷疄浜哄０**鏄惁楠岃瘉鍙栧喅浜?testdata 瑙嗛涓嬭浇鏄惁瀹屾垚锛堟湰鎶ュ憡 搂2 鏈夊搴旇鍒欏凡娴嬶級銆?
- 绌洪棽鍗歌浇璁℃椂鐢?`time.monotonic()`锛涘嵏杞藉悗鏄惧瓨鐢遍┍鍔ㄥ紓姝ュ洖鏀讹紝娴嬭瘯閲?sleep 0.6s 鍚庨噰鏍枫€?
- `health()` 鍦ㄦā鍨嬫湭鍔犺浇鏃朵細鐪熷疄鍔犺浇锛?鈥?s锛夛紝鍥犳璋冪敤 health() 涔熺畻涓€娆℃椿鍔ㄣ€佷細閲嶇疆绌洪棽璁℃椂銆?
- 闀块煶棰戯紙>10min锛夊垎娈垫祦寮忋€佸苟鍙戝璺?ASR 鏈湪鏈祴璇曡鐩栵紙妯″潡涓哄崟妯″瀷 + 涓茶閿侊級銆?
- 娴嬭瘯鏈熼棿鏈満鏈夊叾瀹冭繘绋嬪崰鐢?GPU/CPU锛涘悇鐢ㄤ緥璁板綍浜?`gpu_util_after`锛岃€楁椂鍋忓ぇ鏃朵互姝ゅ垽鏂€傛湰娆?GPU 绌洪棽锛? MiB / 0%锛夊悗澶嶆祴鐨?120s 鑻辫涓?6.1s锛?9.7x 瀹炴椂锛夈€?
- 宸茬煡鐜鍧戯細缂?cuBLAS 鏃跺悓涓€杩涚▼鍐呯浜屾 cuda 灏濊瘯浼氭案涔呭崱姝伙紱妯″潡宸茬敤棰勬+瓒呮椂瀹堟姢瑙勯伩锛屽苟鏈?T9 璐熷鐓ч獙璇侊紙瀛愯繘绋嬫甯哥粨鏉熴€佸洖閫€ CPU锛夈€?




