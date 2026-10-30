# 驅動腳本存檔(續一百七十一)

開機 → 標題 → START 的實機(instance `lc171a`、`lc171b`,使用者 2026-10-29「永遠核准你進行實機」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點、不進除錯器。
步驟與續一百六十三 lc163a 相同,入口檔沿用 `~/fd2-calllog-s163/entries_3b.txt`;差別是 dosbox-x 換成
`~/fd2-dosbox-calllog2`(`tools/dosbox/fd2_calllog_patch.py --upgrade` 後重編;舊樹 `~/fd2-dosbox-calllog` 保留)
並設 `FD2_HARNESS_CALLLOG_SEGS`。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc171.py` | `run NAME`(poll_title → 截圖 → Return → 8 秒 → 截圖)/ `down NAME`(teardown、取紀錄);時間窗依 NAME 取 `SEGS` | `.wsl_build/lc171_live/<NAME>_CALLLOG.TXT`、`cl/<NAME>_run.json` |
| `dosbox_dos_int21_2c.txt` | DOSBox-X `src/dos/dos.cpp` 的 int 21h AH=2Ch 一段與 `overhead()` 原樣摘錄(第一行是整檔 sha256 與行號) | — |

時間窗(模擬 ms):

- `lc171a`:`1700-2000,2000-2010:x,2010-3400,3700-5000,5000-5010:x,5010-7900`。校準 0x3dfef 約 1781 .. 3186、片頭 delay 3700 以後。
  5000 .. 5010 那段逐條窗事後查到不在 delay 迴圈裡(G 紀錄裡 delay 的 int 21h 在 3700 .. 4100、5700 .. 7900)。
- `lc171b`:`2000-2010:x,3800-3810:x,6300-6310:x`。只錄逐條;校準與 lc171a 對照,delay 取 lc171a 的 G 紀錄裡 int 21h 最密的兩段。

指紋(teardown 之後):lc171a CALLLOG.TXT md5 0323eeb1d98d77814b42148f6bd87a33(357406 行)、
lc171b 2b18d320078a7fbbf8465c4366efdc6f(145176 行);兩次 FD2.EXE 都是 33464c81e6a364fd0660141139aa8e6e。

已知限制:

- teardown 砍掉 DOSBox-X 時最後一筆紀錄只寫了一半(atexit 沒跑到);`calllog_segments.py` 只解析 G / S / I,`ev_s171` 把那一行算成截斷。
- lc171a / lc171b 當時把截圖與 run json 寫在本目錄的 `cl/`,事後搬到 `.wsl_build/lc171_live/cl/`(腳本已改成直接寫那裡)。
