# 驅動腳本與 DOSBox-X 摘錄(續一百七十二)

開機 → 標題 → START → 16 秒的實機(instance `lc172a`、`lc172b`,使用者 2026-10-29「永遠核准你進行實機」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點、不進除錯器。
入口檔沿用 `~/fd2-calllog-s163/entries_3b.txt`,dosbox-x 是 `~/fd2-dosbox-calllog2` 以本輪的 `tools/dosbox/fd2_calllog_patch.py --upgrade`
重編(lc172a 用加了 FD2_CALLLOG_SLICES 的那一版;lc172b 用再加 FD2_CALLLOG_PICEV 的那一版,`nm_handlers_s172.txt` 的 sha256 就是它)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc172.py` | `run NAME`(poll_title → 截圖 → Return → 16 秒 → 截圖)/ `down NAME`(teardown、取紀錄);SEGS / DOS 時間 / PICEV 依 NAME | `.wsl_build/lc172_live/<NAME>_CALLLOG.TXT`、`cl/<NAME>_run.json` |
| `pred172.txt` | 實機前寫的預測 P1 .. P5(跑完不改;結果在 doc98 續一百七十二) | — |
| `dosbox_src_s172.txt` | DOSBox-X 原始碼原樣摘錄,每段第一行 `=== <檔> sha256 <整檔> lines <a>-<b>`(核心迴圈、rep、PIC 切片、I/O 延遲、Sound Blaster DMA_DAC、int 08h callback、TIME、PIT 速率) | — |
| `nm_handlers_s172.txt` | `nm` 對 lc172b 那一版 dosbox-x 的輸出裡 P 紀錄用到的 15 個符號(第一行是二進位的 sha256) | — |

設定(兩次相同,只有 PICEV 不同):

- `FD2_HARNESS_CALLLOG_SEGS=3000-3800,3800-3810:x,3810-6300,6300-6310:x,6310-24000`、`FD2_HARNESS_CALLLOG_SLICES=1`、
  `FD2_HARNESS_DOS_TIME=12:00:54`(FD2.EXE 之前 `TIME`;DOS 秒數 0 落在片頭 delay 裡)。
- `FD2_HARNESS_CALLLOG_PICEV`:lc172a 0、lc172b 1。

指紋(teardown 之後):lc172a CALLLOG.TXT md5 902d74f599b2786af3d1a09e0f47b886(503236 行)、
lc172b 204c139f6a85d6983539d06b7cafbf12(497115 行);兩次 FD2.EXE 都是 33464c81e6a364fd0660141139aa8e6e。

已知限制:

- `dosbox_src_s172.txt` 摘錄時樹已經修補過:`src/hardware/pic.cpp` 747 .. 790 行含本地掛勾(`fd2calllog_picevent`),`src/cpu/cpu.cpp` 也含續一百七十一的掛勾;sha256 是修補後的檔。
- 鍵盤 IRQ 若在 selector 0080 收,處理程式最後一段與返回的那段同 selector,G 紀錄併成一段,切不出處理的條數(`ev_s172` 記成 merged)。
- START 那一下 Return 為什麼四次實機都剛好撞上 DIG 型重入,沒有解釋(紀錄裡兩者相隔 0.017 ms)。
