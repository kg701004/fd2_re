# 驅動腳本與人工標記(續一百六十九)

續一百六十八的三個仍留(使用者 2026-10-30「依照你的建議自動繼續進行處理」;實機沿用 2026-10-29「永遠核准你進行實機」)(DOSBox-X)。
實機只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點、不進除錯器;
只把 instance 工作目錄的 FD2.SAV 複本章節設 1(`patch_chapter`,`~/fd2-run` 不動)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `hud_labels.txt` | `drivers_s168/calib_frames.txt` 827 張中畫面上有 HUD 框的 139 張與所在側(人工目視;方法寫在檔頭) | — |
| `mut_frame.py` | 對 `tools/fd2_chapter_sweep.py` 新增的 HUD 邊框樣板做 9 個變異,每個都必須讓 `--selftest` 失敗 | — |
| `pred169_select.txt` | 實機前寫的預測 S1 .. S6(2026-10-30 02:42:51 量 md5,實機 02:42:56 開始;之後沒改,md5 21ab7bd7a3157df7da843f3f0e2b8a8a) | — |
| `lc169.py` | `entries`(lc168 的 26 個入口 + 0x18890 + 0x17aed)/ `run`(進第 1 章戰場 → 清對話只在面板上按,一讀到 E 0x117e7 就送一次 Return → sel_0 → Up → sel_up)/ `down`(teardown、取紀錄) | `.wsl_build/lc169_live/lc169a_CALLLOG.TXT`、`lc169a_run.json`、`frames/` |

當時的步驟:縮圖總表人工標記(`.wsl_build/s169_review/`,不提交)→ 改工具、`--selftest`、`mut_frame.py` 9/9 → `lc169.py entries`
→ 寫 `pred169_select.txt` 並量 md5 → `lc169.py run lc169a`(rc 0)→ `lc169.py down lc169a`。
`lc169a_meta.txt` 是 teardown 之後在 WSL 取的指紋(CALLLOG.TXT 與 FD2.EXE 的 md5、行數、表頭、入口檔)。

已知限制:

- `run` 在送那一次 Return 之前沒有讀 CALLLOG 尾端,所以預測 S3 的後半無法照原寫法判定;`ev_s169` (C) 改用送鍵後的讀數換算送鍵時刻。
- 送鍵的觸發是「這張截圖的 grep 已看到 E 0x117e7」;grep 本身要幾百毫秒,HUD 在這段時間畫出了(S5 FAIL)。
