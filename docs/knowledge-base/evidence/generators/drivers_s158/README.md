# 驅動腳本存檔(續一百五十八)

續一百五十八只有第 5 項第 4 次跑了實機(instance `lc157f`),其餘(第 2 項的鏡頭與地形層、BIOS tick 間隔)是用續一百五十七的呼叫紀錄離線重算,
在 `ev_s158.py` 裡,沒有另外的腳本。只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu` 使用;
只改 DOSBox-X 模擬器記憶體(單位資料、索爾 HP),程式碼不動。使用者 2026-10-27「未確認的部分依建議逐項自動處理」;失敗後依規則停止,沒有重試。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `ret157b.py` | 第 5 項:`entries`(標題序列、讀鍵、delay 等 14 個 EIP)/ `launch`(`FD2_HARNESS_CALLLOG_ICOUNT=1`、`_GATE` = `show_result_resource_79` 0x22e5c)/ `sol1`(索爾 HP = 1,讀回比對)/ `loop`(lc131a 的清對話迴圈 + 每次送鍵 / 截圖計時)/ `post` / `pull` | `.wsl_build/lc157_live/lc157f_title_calllog.txt`、`lc157f/sol1.out` |
| `pred157_item5.txt` | 第 5 項量之前寫下的預測 P1 .. P5;這次沒有走到 GAME OVER,全部 NOT TESTED | — |

當時的步驟:`ret157b.py entries` → `launch lc157f` → `lc157.py hud` → `lc157.py arm lc157f 0 11:1 12:2 13:5 14:7 15:3 16:6`
(`drivers_s157/lc157.py`)→ `ret157b.py sol1` → `lc157.py endturn`。`loop` 與 `post` 沒有跑(結束回合後沒有 GAME OVER)。

已知限制:

- `lc157f/units_after_endturn.out` 是結束回合後 `lc157.py units` 的終端輸出,當時以 `sed` 只留了 11 列。
- 索爾 HP 1 → 200 的來源沒有找到;第 1 次(lc157b)也是如此,第 4 項成功的 lc157 是第 3 回合以後。
