# 驅動腳本(續一百七十三)

開機 → 標題 → START → 16 秒的實機(instance `lc173a`,使用者 2026-10-29「永遠核准你進行實機」)(DOSBox-X),用來驗本輪新建的
`FD2_CALLLOG_IO` / `FD2_CALLLOG_KBD`(`tools/dosbox/fd2_calllog_patch.py`)與 `tools/ail_driver_disasm.py`。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點、不進除錯器。
入口檔沿用 `~/fd2-calllog-s163/entries_3b.txt`;dosbox-x 是 `~/fd2-dosbox-calllog3`(`~/fd2-dosbox-calllog2` 的複本,以本輪的
`fd2_calllog_patch.py --upgrade` 重編,二進位 sha256 12294f935c522a52941deab2b4eb7d904c0a8f606141c2a7dcaf51d92167cba0;calllog2 留給續一百七十二)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc173.py` | `run NAME`(poll_title → 截圖 → Return → 16 秒 → 截圖)/ `down NAME`(teardown、取紀錄) | `.wsl_build/lc173_live/<NAME>_CALLLOG.TXT`、`cl/<NAME>_run.json` |
| `pred173.txt` | 實機前寫的預測 P1 .. P4(跑完不改) | — |
| `dosbox_src_s173.txt` | `ev_s173` 引用的 DOSBox-X 原始碼摘錄(單一樣本 DMA 判準、DSP 0xb0 .. 0xcf / 0xd0 / 0xd4、DMA 計數暫存器、KEYDELAY、STI 多做一條) | — |
| `nm_handlers_s173.txt` | `~/fd2-dosbox-calllog3` 二進位的 nm 子集(P 紀錄的 PIC 事件處理函式) | — |

設定:`FD2_HARNESS_CALLLOG_SEGS=3000-3150,3150-3250:x,3250-24000`、`FD2_HARNESS_CALLLOG_SLICES=1`、`FD2_HARNESS_CALLLOG_PICEV=1`、
`FD2_HARNESS_CALLLOG_IO=0-f,20-21,40-43,60,64,81-8f,a0-a1,c0-df,220-22f,388-38b`、`FD2_HARNESS_CALLLOG_KBD=1`、`FD2_HARNESS_DOS_TIME=12:00:54`。

指紋(teardown 之後):lc173a CALLLOG.TXT md5 3a8bb8b852d99b3f6307a64306408efb(938163 行);FD2.EXE 33464c81e6a364fd0660141139aa8e6e。

已知限制:

- `dosbox_src_s173.txt` 摘錄時樹已經修補過:`src/hardware/keyboard.cpp` 含本地掛勾(`fd2calllog_key`),sha256 是修補後的檔;
  摘錄的行不含掛勾本身。
- O / N 的 eip:CPU 的 in / out 是指令本身;DOSBox-X callback(C++ 的 BIOS 程式)自己做的 I/O 是 callback 指令(FE 38)之後 4 個位元組
  (`ev_s173` (B))。
- 預測 P3 的句子「(計數 + 1)小於一個樣本」差一(實際計數 + 1 = 2 = 一個 16 位元立體聲樣本);括號引的 DOSBox-X 判準(basecnt 比)成立,
  `ev_s173` 兩者都記。
