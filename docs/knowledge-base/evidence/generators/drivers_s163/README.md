# 驅動腳本存檔(續一百六十三)

③b 實機一次(instance `lc163a`,使用者 2026-10-29「還沒做的兩件 請依照你的建議自動進行處理」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `pred163_3b.txt` | 實機前寫的預測 P1 .. P4 與入口清單(之後沒改) | — |
| `lc163.py` | `entries`(寫入口檔)/ `run`(開 instance、poll_title、START、等 8 秒,instance 保留)/ `down`(teardown、取紀錄) | `.wsl_build/lc163_live/lc163a_CALLLOG.TXT`、`lc163a_run.json` |

當時的步驟:`lc163.py entries` → `lc163.py run lc163a`(標題第 7 次輪詢到、START 後進新遊戲開場)→ `lc163.py down lc163a`。
`lc163a_meta.txt` 是 teardown 之後在 WSL 取的指紋(CALLLOG.TXT 與 FD2.EXE 的 md5、行數、表頭、入口檔)。

已知限制:teardown 砍掉 DOSBox-X 時最後一筆 A 記錄只寫了一半(沒有 t),結束時的 C 計數也沒寫出;`ev_s163` 只用 E / R / A 記錄。
