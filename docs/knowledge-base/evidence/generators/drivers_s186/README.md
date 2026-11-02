# 驅動腳本(續一百八十六)

實機一次(instance `lc186a`,使用者 2026-11-02「請進行實機確認」;正常結束)(DOSBox-X)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu`;不改記憶體、不下斷點,單位表與旗標以 debugger 當下讀出。
dosbox-x 與入口檔同 lc184(`~/fd2-dosbox-calllog4`、`~/fd2-calllog-s184/entries_all.txt`,全部 1356 個);不開觸發擷取。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc186.py` | `run NAME [CHAPTER]` / `key` / `hud` / `endturn` / `watch` / `count` / `mem` / `flags` / `down` | `.wsl_build/lc186_live/lc186a_CALLLOG.TXT`、`cl/lc186a/*.png|*.bin`、`cl/lc186a_keys.jsonl` |
| `pred186.txt` | 實機前寫的預測 Q1 .. Q3(跑完不改) | — |

- 順序:`run lc186a 10` → `key` Down / Return / Return(LOAD slot 0「第十一章 幻之森林」)→ 城鎮 Right ×3、Return(出口)、Return(YES)
  → `hud c01_hud`(戰前對話,面板上才按 Return,29 次)→ `mem m00_globals 1efa40 200`、`flags f01_flags`
  → 每回合 `endturn tNN_end` + `watch tNN_enemy 6 540` + `flags fNN_flags`(4 回合);第 2、4 回合後 `mem uNN_units 26c8bc be0`;`down`。
- `f00_flags` 作廢:第一版 `flags` 把 [0x53ad5] 的值再加 0x19c000,讀到 0x392c5c(全 0)。記憶體裡的指標值本身就是線性位址(單位表指標 0x26c8bc 同樣直接讀),已改。
- 設定:`_CAP=3000`、`_DUMP=32`、`_ICOUNT=1`、`_SLICES=1`、`_PICEV=1`、`_KBD=1`、DOS 時間 12:00:54。

指紋(teardown 之後):lc186a md5 86f4fa18d310c54d6146b9ece5a573dd(596430 行)。結果與判準在 `../ev_s186.py`(`../mut_s186.py`)。
