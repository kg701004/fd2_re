# 驅動腳本(續一百九十一)

實機五次(instance `lc191a` .. `lc191e`,使用者 2026-11-04「open_static 7 項、open_live 2 項 請完整進行驗證及處理」;「永遠核准」)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改遊戲記憶體、不下斷點,狀態以 debugger 當下讀出。
dosbox-x 同 lc186(`~/fd2-dosbox-calllog4`);入口檔是本輪的 25 個入口(`ENTRIES`,寫到 `~/fd2-calllog-s191/entries.txt`),上限 2000000;開 KBD(K 紀錄)。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc191.py` | `run NAME [CHAPTER]` / `key` / `xkey` / `hud` / `text` / `state` / `marks` / `goto` / `endturn` / `tstate` / `inject` / `kbd` / `calls` / `down` | `.wsl_build/lc191_live/lc191?_CALLLOG.TXT`、`cl/lc191?/*.png|*.bin|*.json|*.text.json`、`cl/lc191?_keys.jsonl` |
| `pred191.txt` | lc191a 跑之前的預測 Q1 .. Q7 | — |
| `pred191b.txt` | Q1 前提被推翻後、行動結束前寫的 R1 .. R6(取代 Q1 .. Q7) | — |
| `pred191c.txt` | town gate 的 T1 .. T12(每一段補記都寫在該步驟之前) | — |

- 畫面文字一律由 `tools/fd2_screen_text.py` 程式判讀(每張截圖旁存 `.text.json`),不目視。
- `inject` 只寫 BIOS 鍵盤緩衝(BDA `0x41a .. 0x43d`,空緩衝才寫,寫後讀回),等於送一個鍵,不動遊戲記憶體。

實際順序:
- lc191a(ch27,槽 0):`run` → `key` Down Return、Return(槽 0)→ 營地 Right ×3、Return(出口)、Return(YES)→ `hud c01_hud` → `state s00`
  → 選亞雷斯 (14,55)、`marks` → `goto g02 26 39` → Return(移動)→ `state s01` → ↓ Return(休息)→ `state s02` → `goto g03 26 40` → `endturn e01`
  → 等敵方階段 → `state s04` → `goto g04 15 54` → `endturn e02` → `state s05` / `s06`(event63 之後)→ 第 3 回合 `state s07` → `goto g05`
  在第 26 步讀游標失敗(real mode),之後串接的 Return / Down 已盲送 → 停止 → `down`。
- lc191b(ch03):LOAD → `tstate ts00` → `key ctrl+F1` → Left → `key ctrl+F2` → `xkey ctrl+F2` → `key F2` → `key ctrl+F5`(各步之後 `kbd` / `tstate`)→ `down`。
- lc191c(ch03,帶只列 7 個事件的 mapper 檔):LOAD 的鍵都沒進 guest,debugger 也開不了 → `down`。
- lc191d(ch03):LOAD → Left → `inject i01 5f00` → `inject i02 6200` → `down`。
- lc191e(ch06):LOAD → `inject j01 6200`(sel 0)→ Right → `inject j02 6200`(sel 4)→ `down`。

結果與判準在 `../ev_s191.py`(`../mut_s191.py`)。CALLLOG md5(teardown 之後):lc191a f5e060d46ba0598d6912c7472eb8fc82、
lc191b 06ecabbc345421546124d228831c22a8、lc191c e855b8e29b161bb465106950f6c4bfbe、lc191d 3063cd50768ca91f40df2c20dd1f7a6f、
lc191e c2387a3a149257bc75300600f9c9da97。
