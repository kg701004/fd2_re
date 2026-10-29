# 驅動腳本存檔(續一百六十六)

戰場實機一次(instance `lc166a`,使用者 2026-10-29「核准戰場跑實機的部分」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點;
只把 instance 工作目錄的 FD2.SAV 複本章節設 1(`patch_chapter`,`~/fd2-run` 不動)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `pred166_battle.txt` | 實機前寫的預測 P1 .. P4(18:50:49 寫,實機約 18:51:34 開始;之後沒改) | — |
| `lc166.py` | `entries`(寫入口檔:lc163a 的 19 個 + redraw 0x11cac)/ `run`(patch_chapter 1 → 讀檔 → 城鎮 → 續一百零八 `cl.py battle` 的 9 個按鍵 → 閒置 30 秒 → 截圖,instance 保留)/ `down`(teardown、取紀錄) | `.wsl_build/lc166_live/lc166a_CALLLOG.TXT`、`lc166a_run.json`、`lc166a_after_idle.png` |

當時的步驟:`lc166.py entries` → `lc166.py run lc166a` → `lc166.py down lc166a`。
`lc166a_meta.txt` 是 teardown 之後在 WSL 取的指紋(CALLLOG.TXT 與 FD2.EXE 的 md5、行數、表頭、入口檔);
`run` 結束時 CALLLOG.TXT 13556782 bytes,teardown 時 19969498 bytes(instance 一直跑到 teardown),指紋取 teardown 之後的。
`lc166a_r05_enter_battle_prompt.png` 是第 6 個按鍵後的截圖(「要進入戰場嗎?」),之後的 Return 選 YES。

已知限制:

- 最後的畫面是第 1 章戰場地圖上的開場劇情對話(等 Return),不是玩家回合;量到的是對話期間的負載。
- 預測檔的失敗條件寫「截圖不是戰場地圖 → 停止」:畫面是戰場地圖加對話框,redraw 0x11cac 在進戰場後被呼叫 71 次,判定為有進戰場。
- teardown 砍掉 DOSBox-X 時最後一筆記錄只寫了一半(沒有 t);`ev_s166` 只用有 t 的 E / R / A 記錄。
