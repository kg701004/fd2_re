# 驅動腳本存檔(續一百六十七)

戰場回合實機(instance `lc167a`,使用者 2026-10-29「永遠核准你進行實機」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點、不進除錯器;
只把 instance 工作目錄的 FD2.SAV 複本章節設 1(`patch_chapter`,`~/fd2-run` 不動)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `pred167_turns.txt` | 實機前寫的預測 P1 .. P6(22:07:07 寫,實機 22:08 開始;之後沒改,md5 ecf9abcb043fccd40eca5fa60bb8279c) | — |
| `lc167.py` | `entries`(lc166a 的 20 個 + 回合標記 6 個)/ `run`(進第 1 章戰場 → `ensure_battle_hud` → 閒置 30 秒 → 結束回合 → 等 R 0x1d8ba → 閒置 25 秒)/ `down`(teardown、取紀錄) | `.wsl_build/lc167_live/lc167a_CALLLOG.TXT`、`lc167a_run.json` |
| `step.py` | 第一次結束回合失敗後,在同一個 instance 逐鍵送鍵、截圖、記 CALLLOG 尾端的 t | `lc167a_steps.jsonl`、`lc167a_step_*.png` |
| `finish.py` | 在「要結束本回合的行動嗎?」按 YES → 等 R 0x1d8ba → 閒置 25 秒(P2) | `lc167a_finish.json`、`lc167a_enemy_wait_04.png`、`lc167a_p2_idle_end.png` |

當時的步驟:`lc167.py entries` → `lc167.py run lc167a`(結束回合沒成功,rc 1)→ `step.py lc167a esc Escape` → `step.py lc167a close Return`
→ `step.py lc167a ring Down Return` → `step.py lc167a end Down Return` → `finish.py lc167a` → `lc167.py down lc167a`。
`lc167a_meta.txt` 是 teardown 之後在 WSL 取的指紋(CALLLOG.TXT 與 FD2.EXE 的 md5、行數、表頭、入口檔)。

已知限制:

- `run` 的結束回合:`find_empty_adjacent_tile` 往上找到空格,但之後的按鍵沒開出指令環(0x16f55 沒進入),停在索爾的狀態畫面
  (`lc167a_wait_46_status_screen.png`)。推測是 `ensure_battle_hud` 多按了一次 Return 選中索爾(`lc167a_findempty_001_Up.png` 地圖整片變暗)。
- P 窗口是在索爾選中、等目的地的狀態下閒置;P2 是一般的游標閒置。兩者比例相差 0.015 個百分點。
- teardown 砍掉 DOSBox-X 時最後一筆記錄只寫了一半(沒有 t);`ev_s167` 只用有 t 的 E / R / A 記錄。
