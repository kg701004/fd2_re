# 驅動腳本存檔(續一百五十七)

續一百五十七在 DOSBox-X / WSL 上產生 `.wsl_build/lc157_live/` 原始紀錄的腳本。每支只在第一行加了存檔說明,其餘內容不改;
路徑保留當時的工作環境(scratchpad `s157/`、WSL `~/fd2-calllog-s157/`、harness instance `lc157` .. `lc157e`)。
只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)、WSL `-d Ubuntu` 使用;只改模擬器記憶體(單位資料、`[0x53af9]`、
調色盤緩衝的索引 255、索爾 HP),程式碼不動。使用者 2026-10-27 核准這 6 項實機;第 2 項第二輪擺法(lc157e)另經核准重跑。

| 檔 | 用途 | 產生的原始紀錄 |
|---|---|---|
| `lc157.py` | 第 3 項:`entries` / `launch` / `hud` / `arm`(敵 #11 .. #16 各只會一個法術、`[0x53af9]` 設 1 或 0)/ `endturn` / `log`;第 1 項:`grey`(改單位 +2、+5)、`dump`(畫面、調色盤、單位、捲動、時脈)、`sprtab`(`[0x53a61]` 單位圖快取) | `cells_1257_calllog.txt`、`units_after_neg.txt`、`grey1_*`、`grey2_*`、`sprtab.bin` |
| `dac157.py` | 第 4 項:在 0x1fc7b / 0x1fd64 下斷點、索爾 HP 設 1、結束回合;停下後讀硬體 DAC(除錯器 `VGA DACPAL`)與 `[0x53a65]` 緩衝,把緩衝索引 255 改成 (1, 2, 3),停在返回處再讀一次 | `dac255_1fc7b.json` |
| `lc157t.py` | 第 2 項:`entries` / `launch`(`FD2_HARNESS_CALLLOG_ICOUNT=1`、`_GATE` = ai_item_action)/ `hud` / `arm` / `armC`(第二輪擺法,寫入後逐欄讀回)/ `check` / `endturn` / `laps` / `pull` | `lc157{c,d,e}_redraw_icount.txt`、`lc157e_armC.out`、`lc157e_check.out` |
| `pred157_item2.txt` | 第 2 項量之前寫下的預測 P1 .. P5(15:45 寫,第一份紀錄 lc157c 在 15:50 取回);`ev_s157.py` 逐項判定 | — |

`lc157.py`、`dac157.py`、`lc157t.py` 匯入的 `live.py`、`cl.py`、`lc130.py`、`lc131.py`(scratchpad 根目錄或 `s157/` 那一份)
與 [`drivers_s100_s133/`](../drivers_s100_s133/README.md) 的存檔內容相同(根目錄那份少第一行說明;`s157/` 的 `cl.py`、`live.py`
就是從存檔複製的,逐 byte 相同),這裡不重複存。

已知限制:

- `lc157e_armC.out` / `lc157e_check.out` 是 `lc157t.py armC` / `check` 的終端輸出(從 scratchpad 複製到 `.wsl_build/lc157_live/`)。
- lc157d 原本要跑第二輪擺法:當時的 `armC` 在讀回時 `mem dump` 沒產生檔,驅動以管線接著跑 `endturn`,記憶體寫入沒有落地,
  量到的是第一輪擺法。`lc157t.py` 之後改成先刪讀回檔、逐 byte 比對、每步檢查結束碼,lc157e 才是第二輪擺法。
- 第 5 項(第 18 次 Return)三次都沒讓索爾倒下、沒走到 GAME OVER,沒有可用的紀錄;那一項的腳本不存。
