# 驅動腳本存檔(續一百六十八)

戰場驅動送鍵閘門的實機驗證(instance `lc168a`,使用者 2026-10-29「永遠核准你進行實機」、「依照你的建議執行」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點、不進除錯器;
只把 instance 工作目錄的 FD2.SAV 複本章節設 1(`patch_chapter`,`~/fd2-run` 不動)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `pred168_gates.txt` | 實機前寫的預測 Q1 .. Q6(2026-10-30 00:05:17 量 md5,實機 00:05:28 開始;之後沒改,md5 0449c05fc75c73179000361e71431a04) | — |
| `lc168.py` | `entries`(與 lc167 相同的 26 個入口)/ `run`(進第 1 章戰場 → `ensure_battle_hud(panel_gate=True)` → 狀態檢查 → 閒置 30 秒 → `send_end_turn_keys` → 等 R 0x1d8ba → 閒置 25 秒)/ `down`(teardown、取紀錄) | `.wsl_build/lc168_live/lc168a_CALLLOG.TXT`、`lc168a_run.json`、`frames/` |
| `scan_frames.py` | 校準 `screen_shows_dialogue_panel`:掃 `.wsl_build` 與 lc167a 的 hudcheck 截圖,算上 / 下帶的藍色比例與單一 HUD 藍佔比 | 清單固定在 `calib_frames.txt`(827 張) |
| `calib_frames.txt` | `ev_s168` (B) 讀的校準截圖清單(倉庫相對路徑;lc167a 那 34 張 hudcheck 已從 scratchpad 複製到 `.wsl_build/lc167_live/frames/`) | — |
| `mut_gates.py` | 對 `tools/fd2_chapter_sweep.py` 新增的判準與閘門做 12 個變異,每個都必須讓 `--selftest` 失敗 | — |

當時的步驟:`scan_frames.py`(校準)→ 改工具、`--selftest`、`mut_gates.py` 12/12 → `lc168.py entries` → `lc168.py run lc168a`(rc 0)→ `lc168.py down lc168a`。
`lc168a_meta.txt` 是 teardown 之後在 WSL 取的指紋(FD2.EXE 與 CALLLOG.TXT 的 md5、行數、表頭、入口檔)。
`.wsl_build/lc167_live/frames_mtime.json` 是 lc167a 原始截圖(scratchpad)的 mtime,`ev_s168` (C) 用來換算截圖時刻。

已知限制:

- 驅動讀 CALLLOG 的判斷(`control_probe`、`ring_probe`、狀態檢查)會落後約 2 秒(寫入端每 1024 筆 E 才 fflush),所以都是輪詢加逾時;
  狀態檢查前先等 3 秒。
- 截圖複製到 `.wsl_build` 後 mtime 不可靠,`ev_s168` 依 panel_gate 的規則重建 lc168a 的截圖順序。
