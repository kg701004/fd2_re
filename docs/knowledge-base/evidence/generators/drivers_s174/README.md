# 驅動腳本(續一百七十四)

開機 → 標題 → START → 16 秒的實機兩次(instance `lc174a`、`lc174b`,使用者 2026-10-29「永遠核准你進行實機」)(DOSBox-X),
用來驗本輪新加的觸發式擷取 `FD2_CALLLOG_TRIG`(`tools/dosbox/fd2_calllog_patch.py`)與 `tools/calllog_segments.py trig`。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點、不進除錯器。
入口檔沿用 `~/fd2-calllog-s163/entries_3b.txt`;dosbox-x 是 `~/fd2-dosbox-calllog4`(`~/fd2-dosbox-calllog3` 的複本,
以本輪的 `fd2_calllog_patch.py --upgrade` 重編;calllog3 留給續一百七十三)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc174.py` | `run NAME` / `down NAME`(步驟同 lc173:poll_title → 截圖 → Return → 16 秒 → 截圖;teardown、取紀錄) | `.wsl_build/lc174_live/<NAME>_CALLLOG.TXT`、`cl/<NAME>_run.json` |
| `pred174.txt` | 實機前寫的預測:P1 .. P3 在 lc174a 之前,P4 .. P6 在 lc174a 之後、lc174b 之前(跑完不改) | — |
| `check174.py` | 兩份紀錄對 P1、P2、P4 .. P6 逐項 assert(先比 md5;解析與區塊自核用 `calllog_segments`) | — |

設定(兩次相同的部分與 lc173a 一樣):`FD2_HARNESS_CALLLOG_SEGS=3000-3150,3150-3250:x,3250-24000`、`_SLICES=1`、`_PICEV=1`、
`_IO=0-f,20-21,40-43,60,64,81-8f,a0-a1,c0-df,220-22f,388-38b`、`_KBD=1`、`FD2_HARNESS_DOS_TIME=12:00:54`;
`FD2_HARNESS_CALLLOG_TRIG=if:40000-,ng:600-604,ng:375,if:1000-2000@0070`、`_TRIGCAP=8`;lc174b 另加 `_TRIGT=9500-24000`。

二進位:lc174a 用第一版(md5 32d4aa4de5e4d0ada769e5c204144b80,留在 `~/fd2-dosbox-calllog4/dosbox-x/src/dosbox-x.lc174a`);
lc174b 用修正後的版本(sha256 882925130480c1eaf2e5e366c867bd880ad50a6f801202e1fcb6cea073a4f592)。

指紋(teardown 之後):lc174a CALLLOG.TXT md5 0aaee51798ec85a779a95aa78ed85cac(1325050 行,最後一行寫到一半);
lc174b md5 9be49f776cc0ed2fbbc3d7e962503b14(1185411 行,最後一行寫到一半);FD2.EXE 33464c81e6a364fd0660141139aa8e6e。

已知限制:

- harness 收尾是砍掉模擬器(不跑 atexit):兩份紀錄的最後一行都寫到一半,`calllog_segments._read` 丟掉那一行(`tail_cut`)。
  lc174a 用的第一版只在結尾寫 YC / YN,所以 lc174a 沒有統計;修正版每寫一個區塊與每 >= 1000 ms 寫一組並 flush(lc174b 有)。
- lc174a 每條規則 8 個的上限在 START 之前用完(START 那一刻的 DIG 型區塊沒寫出),lc174b 用 TRIGT 只算 9500 ms 之後。
- 沒有證據產生器(ev_s174)與變異測試;`check174.py` 只是逐項 assert,`trig_problems` 的判準在 `calllog_segments --selftest` 裡有故障注入。
