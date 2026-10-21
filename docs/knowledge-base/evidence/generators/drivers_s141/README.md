# 驅動腳本存檔(續一百四十一)

續一百四十一在 DOSBox-X / WSL 上產生 `.wsl_build/s141_demonface/` 原始紀錄的腳本。檔頭(shebang 之後)加了「存檔」一行,其餘內容不改;
路徑保留當時的工作環境(WSL `~/s141/`、harness instance `s141t`),不保證能直接執行。只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、
WSL `-d Ubuntu` 使用,不送任何按鍵。

| 檔 | 原檔 sha256(前 16 碼) | 對話紀錄裡的執行 | 用途 |
|---|---|---|---|
| `burst_s141.sh` | `d6420fa6317e9c74` | `b 35.5 4`、`c 39.5 4`(2026-10-21);`a 31 4` 用的是更早一版(輸出到 `/tmp/s141_shots_a`,其餘相同) | 等 harness 狀態檔 `STATUS=running` 起算 t0,sleep 後以 `import -window root` 連拍;`c` 段的 93 張是 `ev_s141.py` 的輸入 |

harness 啟動:`MSYS_NO_PATHCONV=1 wsl -d Ubuntu bash tools/dosbox_harness.sh launch s141t 400`(`core=normal`、`cycles=5000`)。

已知限制(續一百四十二):

- 檔名的時間是呼叫 `import` 之前取的;一次截圖約 0.04 秒,實際截取時刻晚一點。
- 截圖與 DOSBox-X 畫面更新不同步,而且遊戲複製畫面(`0x11eb0`)不等垂直同步,所以會拍到撕裂幀;`ev_s141.py` 以「每個像素來自 dy - 1 / dy / dy + 1」解釋。
- 拍攝時段是用前兩段試拍定位的,沒有先對照 title_seq 的觸發表(doc39 §10.5)。`c` 段在 esi == 0x19 的 ANI #0 插播途中結束,
  esi 24 → 0、浮空城插播(`0x1fba4 cmp esi,0xa`)、esi == 0 的停留(`0x1fc4c`)與之後的轉場都沒在 DOSBox-X 拍到。下次要拍這幾段,先用觸發表(每步約 42 ms,實測 23.6 列 / 秒)
  與 ANI 插播的長度算出時段再拍。
