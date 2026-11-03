# 驅動腳本(續一百八十八)

實機一次(instance `lc188a`,使用者 2026-11-03「永遠核准」;正常結束)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點,旗標、金錢、游標、單位表以 debugger 當下讀出。
dosbox-x 與入口檔同 lc186(`~/fd2-dosbox-calllog4`、`~/fd2-calllog-s184/entries_all.txt`);不開觸發擷取。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc188.py` | `run NAME [CHAPTER]` / `key` / `hud` / `text` / `state` / `goto` / `down` | `.wsl_build/lc188_live/lc188a_CALLLOG.TXT`、`cl/lc188a/*.png|*.bin|*.json|*.text.json`、`cl/lc188a_keys.jsonl` |
| `pred188.txt` | 實機前寫的預測 Q1 .. Q3(跑完不改) | — |

- 畫面文字一律由 `tools/fd2_screen_text.py` 程式判讀(每張截圖旁存 `.text.json`),不目視。
- 預定順序:`run lc188a 10` → `key` Down / Return / Return(LOAD slot 0「第十一章 幻之森林」)→ 城鎮 Right ×3、Return(出口)、Return(YES)
  → `hud c01_hud` → `state s00` → `goto` 到 slot 9 (3,8) 最近的己方單位、Return 選取 → `goto` (3,8)、Return
  → 指令環 Down、Return → `text`(要看到 0x1a5)→ `state s01` → `key t02` Return(YES)→ `state s02` → `key t03` Return → `state s03` → `down`。

實際順序(2026-11-03):`run lc188a 10` → `key k01_load` Down / Return / Return → `key k02_exit` Right ×3 → `key k03_exit_confirm` Return(「要進入戰場嗎?」)
→ `key k04_yes` Return → `hud c01_hud`(29 次)→ `state s00`(單位 11 在 (2,10))→ `goto g01 2 10`(Left ×16)→ `key k05_select` Return(索菲亞)
→ `goto g02 3 8`(Right、Up ×2)→ `key k06_move` Return(指令環)→ `state s0r`(單位 11 在 (3,8))→ `key k07_ring_down` Down → `key k08_ring_confirm` Return(0x1a5)
→ `state s01` → `key t02` Return(YES;0x1a5 + 0x1aa、5000)→ `state s02` → `text t02b` → `key t03` Return(沒有字)→ `state s03` → `down`。

結果:s02 旗標[9] 0、錢 10070183、[0x53ae1] 5000;s03 旗標[9] 1、錢 10075183。pred188.txt Q1 .. Q3 全部成立。
指紋(teardown 之後,`lc188a_fingerprint.txt`):FD2.EXE md5 33464c81e6a364fd0660141139aa8e6e;CALLLOG md5 2908f21531128deb5900a435460ccd9f(381714 行)。
結果與判準在 `../ev_s188.py`(`../mut_s188.py`)。
