# 探針、截圖清單與人工判讀(續一百七十)

續一百六十九 / 一百六十七的仍留(使用者 2026-10-30「依照你的建議自動繼續進行處理」)。這一輪不跑實機;
WSL 只用來跑 glibc 探針,不碰 `~/fd2-run-harness-*` 的內容(只讀 stat)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `setvbuf_probe.py` | 在 WSL 對 DOSBox-X 連結的同一份 glibc 照 CALLLOG 的寫法 `setvbuf(NULL, _IOFBF, 1 MiB)`,逐筆看檔案大小(對照:明確給 1 MiB buf、不呼叫 setvbuf) | `setvbuf_probe_out.txt`(本目錄,`ev_s170` (A) 逐行核對) |
| `select_uncovered.py` | 從 `.wsl_build` 挑出路徑章節標記不在 827 張校準集內的 1024x768 截圖,依像素去重,列出樣板吻合率與舊藍佔比判準 | `uncovered_frames.txt`(3015 張);逐張數值在 `.wsl_build/s170_review/hud_scan.csv`(不提交) |
| `mut_frame.py` | 續一百七十版的 HUD 邊框樣板變異(`drivers_s169/mut_frame.py` 其中 2 個的目標程式碼已拿掉;保留 7 個、加「加回退回藍佔比」),每個都必須讓 `--selftest` 失敗:8 / 8 | — |
| `hud_labels_s170.txt` | 舊藍佔比判準判有、樣板判沒有的 348 張(一律 N),與樣板判有框的抽樣 66 張(L / R)的人工目視判讀;方法寫在檔頭 | — |

當時的步驟:`setvbuf_probe.py`(`wsl -d Ubuntu -- python3 …`,輸出導到 `setvbuf_probe_out.txt`)→ `select_uncovered.py`
(掃 7937 張、去重 3015 張)→ 下方地圖帶拼成縮圖總表(`.wsl_build/s170_review/`)逐張看 → 寫 `hud_labels_s170.txt`
→ 改 `tools/fd2_chapter_sweep.py`(只看樣板)、`--selftest`、`mut_frame.py` 8 / 8、`verify_selftest_discrimination.py --exhaustive --tool
fd2_chapter_sweep.py` 歸零 → `ev_s170.py`。
