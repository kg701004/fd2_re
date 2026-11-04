# 驅動腳本(續一百九十二)

實機七次(instance `lc192a` .. `lc192g`,使用者 2026-11-04「仍未解決 請新建工具 對應處理每個未解決項目」;「永遠核准」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;dosbox-x 同 lc191(`~/fd2-dosbox-calllog4`),
入口檔是本輪的 26 個入口(`ENTRIES`,寫到 `~/fd2-calllog-s192/entries.txt`;非函式入口的分支探針也記 E),上限 2000000,開 KBD。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc192.py` | `run NAME [CHAPTER] [mapper]` / `key` / `text` / `state` / `tstate [SEL]` / `goto` / `endturn` / `hud` / `marks` / `wait` / `poke` / `bpreg` / `calls` / `kbd` / `down` | `.wsl_build/lc192_live/lc192?_CALLLOG.TXT`、`cl/lc192?/*.png|*.bin|*.json|*.text.json`、`cl/lc192?_keys.jsonl` |
| `pred192m.txt` | mapper 實機 M1 .. M8(補 1 / 補 2 寫在改測之前) | — |
| `pred192a.txt` | R6 A1 .. A4、物理攻擊音效 P1 .. P6、會心 C1 .. C3'(補 1 .. 補 3) | — |
| `pred192b.txt` | event 82 E1 .. E5、介入 1 / 2(補 1) | — |

與 lc191 的差別:
- debugger 讀取失敗(lc191a 停在 real mode 的那種)時 resume、等 0.4 s、重進 debugger 重讀,最多 6 次;全部失敗才丟例外,
  該指令不送任何鍵。本輪實機發生 7 次(lc192a 5、lc192b 1、lc192c 1),都在第 2 次讀到(`read_retry` / `read_ok` 紀錄,ev_s192 (C) 核對)。
- `tstate NAME LABEL SEL`:sel 不符就非 0 結束,`&&` 串接的下一個鍵不送(M6b 送錯 selection 之後加的)。
- `poke`:寫一段遊戲記憶體、先讀前值、寫後讀回;`bpreg`:下斷點 → 送鍵 → 停在該 EIP 且核對暫存器相符才 `SR`,一律刪斷點。
  兩者只在預測檔先寫明理由的步驟用(pred192a 補 2 / 補 3、pred192b 介入 1 / 2)。
- `run ... mapper` 帶 `tools/dosbox/passthrough.map`(`tools/dosbox/make_passthrough_map.py` 產生的完整檔)。

實際順序:
- lc192c(章節 byte 2,mapper):LOAD → `tstate` → sel 0 `ctrl+F2`(對照)→ Left → `ctrl+F2` → `down`。
- lc192d(章節 byte 5,mapper):LOAD → Right → `ctrl+F5` → `down`。
- lc192e(章節 byte 19,mapper):LOAD → Right → `ctrl+F10`(M6 FAIL)→ Left → `shift+F9`(sel 0,M6b FAIL)→ Right ×2 → `shift+F9` → `down`。
- lc192f(章節 byte 20,mapper):LOAD → Right → `ctrl+F10` → `down`。lc192g(章節 byte 26,mapper):LOAD → `ctrl+F6` → `down`。
- lc192a(ch27 槽 0,不帶 mapper):lc191a 同路徑到第 3 回合 → 亞雷斯 (26,39) → (25,39) 休息 → 第 4 回合攻擊 71 → 第 5 回合擊殺 71 →
  第 6 回合 `poke` 0x1ee4b3(會心表 [11])→ 攻擊 72 → 寫回 → `poke` 0x1ee4b2([10])→ 結束回合(反擊會心)→ 寫回 → `down`。
- lc192b(章節 byte 29):LOAD → 出擊選人 11 人 → `bpreg` 0x1c70e3 EBP 0x13 → 0xc → YES → 戰場 → `poke` 索引 24 HP → 亞雷斯 (22,19) 攻擊 24
  (擊殺)→ 結束第 1 / 2 / 3 回合 → `down`。

結果與判準在 `../ev_s192.py`(`../mut_s192.py`)。CALLLOG md5(teardown 之後):lc192a a1e50df7bf4fc02e8c48017b16d9ce0d、
lc192b 25244d521dec6935e46e09964e4de388、lc192c a183991bd88e2c8ab58e5915449995a8、lc192d 639e4b5dd6206817f4e398a88a28072c、
lc192e 4cfb7462fe4ae0688226982677e14394、lc192f 89bb242c74ad35b9c3b5887b1a4bf59d、lc192g d5876263d0e5efa0f952d577eecab9b2。
