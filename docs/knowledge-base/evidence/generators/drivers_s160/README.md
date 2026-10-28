# 驅動腳本存檔(續一百六十)

第 5 項第 6 次實機(instance `lc159b`,使用者 2026-10-28 再次核准「第五項 核准授權你重新實機重跑驗證」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;只改模擬器記憶體(索爾 `+5` 的 bit0),程式碼不動,遊戲途中不下斷點。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `step159.py` | 逐鍵送、逐鍵截圖:`shot`(不送鍵)/ `key`(送一個鍵、等、截圖)/ `clear`(一次一個 Return,第一張看到戰場 HUD 就停);每步記主機時間與 `cursor_tile_is_empty` | `.wsl_build/lc159_live/lc159b/steps/`、`lc159b_steps.jsonl` |
| `an159.py` | 離線:列出送鍵(主機時間)、有鍵事件群、讀鍵 / 標題序列事件(模擬時間),用來找對齊方式;結論以 `ev_s160` 為準 | — |

其餘沿用:`drivers_s158/ret157b.py`(`launch` / `post`)、`drivers_s159/ret159.py`(`kill` / `go`)、預測 `drivers_s159/pred159_item5.txt`(這次照原文用)。

當時的步驟:`ret157b.py launch lc159b` → `step159.py shot` → `step159.py clear lc159b 60`(第 32 次 Return 出現索爾資訊框)→ `shot`(3 秒後地圖褪色)
→ `key Escape` → `key Up` → `key Return`(系統指令環)→ `key Down` → `key Return`(「要結束本回合的行動嗎?」)→ `ret159.py kill lc159b`
→ `shot` → `ret159.py go lc159b 45` → `ret157b.py post lc159b`(輸出在 `lc157_live/`,複製到 `lc159_live/`)→ `shot` → teardown。

呼叫紀錄:teardown 之後的完整 `CALLLOG.TXT` 是 10.4 GB、58500104 行(md5 2dbf231b…6b,留在 WSL 的 `~/fd2-run-harness-lc159b/`,不複製),
以 `awk '!($3=="001ac620" && ($1=="E" || $4=="00000000"))'` 去掉 has_key 的 E 記錄與回傳 0 的 R 記錄,剩 2924 行
(`.wsl_build/lc159_live/lc159b_calllog_filtered.txt`);指紋與規則記在 `lc159b_meta.txt`。

已知限制:

- teardown 前曾對還在寫的紀錄做過一次過濾(那時 md5 aa340f4b…、10315578 行);`ev_s160` 讀的是 teardown 之後重做的版本。
- 主機時間是送鍵指令開始的時間(`t0`);鍵實際進到 DOSBox-X 是在 `t0` .. `t1`(約 0.2 秒)之間,對齊的殘差包含這一段。
