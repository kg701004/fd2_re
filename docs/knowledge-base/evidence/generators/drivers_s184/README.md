# 驅動腳本(續一百八十四)

實機兩次(instance `lc184a`、`lc184b`,使用者 2026-11-02「請全部實機執行進行確認」;兩次都正常結束)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點,單位表以 debugger 當下讀出。
dosbox-x 同 lc181(`~/fd2-dosbox-calllog4`);入口檔全部 1356 個(`~/fd2-calllog-s184/entries_all.txt`,`verify_names_by_calllog.py --write-entries`)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc184.py` | `run NAME [CHAPTER]` / `key NAME LABEL WAIT K..` / `mem NAME LABEL LIN LEN` / `down NAME`(逐鍵推進、每次截圖) | `.wsl_build/lc184_live/<NAME>_CALLLOG.TXT`、`cl/<NAME>/*.png|*.bin`、`cl/<NAME>_keys.jsonl` |
| `pred184.txt` | 實機前寫的預測 Q1 .. Q3(跑完不改) | — |

- lc184a:標題 START → 開場逐鍵 Return(第 32 張圖 → 第 31 張圖)→ 第 0 張圖:行動環開 / 收(d01 / d02)、盜賊資訊卡(e01 .. e03)。
- lc184b:slot 0 章節改 1 → LOAD → 城鎮 Return(g01 .. g03)→ 出口 → 戰前對話 → 索爾走到 (19,16) 寶箱格、休息、YES(m01 .. n05)。

設定:`FD2_CALLLOG_TRIG=ng:375,ng:302-303`、`_TRIGCAP=40`、`_CAP=3000`、`_DUMP=32`、`_ICOUNT=1`、`_SLICES=1`、`_PICEV=1`、`_KBD=1`、DOS 時間 12:00:54。

指紋(teardown 之後):lc184a md5 dcbf7cf1a6f579616cb5a709493019f6、lc184b 2fa8a9e680dfc234af04af430f181213。

注意:開場後盲按 Return 會進到行動環 / 法術目標游標(lc184b i27 .. i36),之後要先 Escape 退回自由游標;移動範圍覆蓋層會閃爍,
單張截圖看不出是否在選位置模式,以紀錄裡正在跑的函式(`target_cursor_loop` 等)為準。結果與判準在 `../ev_s184.py`(`../mut_s184.py`)。
