# 驅動腳本存檔(續一百四十五)

續一百四十五在 DOSBox-X / WSL 上產生 `.wsl_build/s145_afterlock/` 原始紀錄的腳本,內容不改;路徑保留當時的工作環境
(WSL `~/s145/`、harness instance `s145t`)。只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu` 使用,不送任何按鍵。
使用者 2026-10-21 核准這一次連拍。

| 檔 | 對話紀錄裡的執行 | 用途 |
|---|---|---|
| `burst_s145.sh` | `c 43.5 22`(2026-10-21) | 等 harness 狀態檔 `STATUS=running` 起算 t0,sleep 43.5 秒後以 `import -window root` 連拍 22 秒(444 張),`times.txt` 記每張 import 前後的相對秒數;是 `ev_s145.py` 的輸入 |

harness 啟動:`MSYS_NO_PATHCONV=1 wsl -d Ubuntu bash tools/dosbox_harness.sh launch s145t 400`(`core=normal`、`cycles=5000`),拍完 `teardown s145t`(workdir 留著)。

拍攝時段依 doc39 §10.5 觸發表與續一百四十一的實拍(金鎖第 21 幀 @ t0 + 44.08)事先算好:金鎖剩 75 幀約 4 秒、esi 24 → 0 約 1 秒、
浮空城插播、停留 1000 ms、轉場與 logo,共留 22 秒。

已知限制:

- 檔名時間是 `import` 之前取的;`times.txt` 另記 import 結束時間(一次約 0.04–0.05 秒)。
- 拍攝時 Windows 端另有 `sweep_literals ev_s141`(單一 worker)在跑;同段捲動速率 23.7 列 / 秒,與續一百四十一無負載的 23.6 相同。
- 淡入淡出時調色盤在掃描途中被改寫,一張實拍可分成多段(最多 40 段),另有 128 張的 2×2 區塊不一致;`ev_s145.py` 以逐列判準處理。
