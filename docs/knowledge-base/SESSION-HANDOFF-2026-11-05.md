# SESSION-HANDOFF 2026-11-05

> 依 `AI_Development_Standard/00_Global/Project_Continuity.md` 撰寫:分開已完成 / 進行中 / 延後 / 需人決定,每一項標驗證等級(依據是原版 FD2.EXE 反組譯與
> 原版在 DOSBox-X 上的呼叫紀錄),不把未驗證的寫成已驗證。前一份:[`SESSION-HANDOFF-2026-10-07.md`](SESSION-HANDOFF-2026-10-07.md)(只交接函式清單那一條線)。

## 0. 範圍

- 涵蓋 2026-10-07 之後的全部工作:commit `29295e6d` .. `538eb6df`(97 個,都已推送到 `fork remaster-local`)加上續一百九十三那一個 commit。
  逐步紀錄在 [`98-tooling-infrastructure.md`](98-tooling-infrastructure.md) 續九十九 .. 續一百九十三;依主題的目錄是 [`98-index.md`](98-index.md)
  (由 `tools/doc98_index.py --write` 產生,不要手改)。
- 研究對象只有原版 `FD2.EXE`(md5 `33464c81e6a364fd0660141139aa8e6e`)。remake 已移除(歷史紀錄見 98-index「remake 時期的工具」)。

## 1. 現況

**已完成(都有證據產生器或工具 selftest 看守)**

| 主題 | 結果 | 驗證等級 | 節次 |
|---|---|---|---|
| 函式清單 | 1356 個入口全部有登錄名稱;`function_inventory.py --selftest` 看守 | CODE CONFIRMED(FD2.EXE 反組譯) | 續八十一 .. 九十五 |
| 函式摘要與參數 | 續一百一十九時具名參數 1525:機器比過 1176、人工讀過 349、都沒有 0 | CODE CONFIRMED(FD2.EXE 反組譯);有 DOSBox-X 呼叫紀錄的部分 LOG CONFIRMED | 續一百零九 .. 一百二十一 |
| 原版實機呼叫紀錄 | 修補的 DOSBox-X(`tools/dosbox/fd2_calllog_patch.py`)記入口參數 / 回傳 / I/O / 按鍵 / 觸發擷取;解析器 `tools/calllog_segments.py` | LOG CONFIRMED(DOSBox-X,非真硬體) | 續一百零七、一百七十一 .. 一百七十七 |
| 畫面 / 換色 / RLE / HUD / LUT | 72 節;四模式 RLE 解碼再編回逐 byte 相同 | CODE + LOG CONFIRMED(FD2.EXE 反組譯、DOSBox-X 實拍) | 續一百二十二 .. 一百五十八 |
| AIL 音訊與計時 | 5 ms 基底 = DIG 服務計時器 0x404c0;重入、關中斷、掉中斷率都有實機量測 | LOG CONFIRMED | 續一百六十一 .. 一百七十六 |
| UI 音效對應 | 打字音、腳步音(依職業)、面板展開 / 收起等 index 全部對到場景 | LOG CONFIRMED(DOSBox-X 呼叫紀錄) | 續一百七十九 .. 一百九十 |
| 事件系統收尾 | event63 不重複、event 81 → 82 派送、物理攻擊每輪音效與會心 | LOG CONFIRMED(DOSBox-X 呼叫紀錄 lc192a / lc192b) | 續一百九十一 .. 一百九十二 |
| 城鎮秘密店 F 鍵 | 完整 pass-through mapper 讓真按的 Ctrl / Shift + F 鍵進 guest | LOG CONFIRMED(DOSBox-X K 紀錄 lc192c .. g) | 續一百九十二 |
| 出擊選人 | 旗標章節名冊不足時無出口;正常劇情碰不到 | CODE CONFIRMED(FD2.EXE 反組譯)+ LOG CONFIRMED(DOSBox-X lc192b)+ STATIC ANALYSIS(名冊下界) | 續一百九十三 |

- worklist(`python tools/worklist_checklist.py --summary`,2026-11-05):勾選框 746 —— `[x]` 631、`[~]` 92、`[ ]` 23;
  分類 closed 44、obsolete_remake 68、not_a_task 3、**open_static 0、open_live 0**。
- 證據產生器:`docs/knowledge-base/evidence/generators/run_all.py` 全部 IDENTICAL(續一百九十二時 90 個;續一百九十三加 `ev_s193`)。

**進行中**:規格層 100% 逆向(使用者 2026-11-05 定的目標;之後再決定要不要做可重編譯原始碼)。分母與核對由 `tools/re_coverage.py` 提供(續一百九十四)。
基準(2026-11-05):遊戲函式 474 / 1202(引用的全域位址全部已登錄)、函式庫 154 / 154、資料區 0 / 35714 bytes、被引用全域位址 0 / 900、
原版檔案 0 / 49、`.DAT` 資源 0 / 1005。登錄在 `docs/data/data_map.json`、`docs/data/resource_map.json`(目前是空的)。
續一百九十五(2026-11-06):登錄第一段 `0x53a45`(active_unit_array,4 byte 指標),遊戲函式 506 / 1202、全域位址 1 / 900;
`--check` 另核對指令層存取寬度(直接定址不得跨出區段)與 `fields`(區段內被引用位址都要命名)。下一批:`0x54153..0x5417c`(AIL 3.02 內部狀態——這句不精確,`0x54153` 不是 AIL,見續一百九十六)。
續一百九十六(2026-11-06):登錄 `0x54153..0x54195` 11 段(`0x54153` 戰鬥演出音效 bank;其餘是 AIL_DEBUG 追蹤狀態,一般執行全停在 0),遊戲函式 507 / 1202、全域位址 11 / 900、資料 44 / 35714 bytes(訂正:實為 13 / 900、70 bytes,見續一百九十七)。下一批:`0x53a79`、`0x538a8` / `0x538b0`、`0x53a49`。
續一百九十七(2026-11-06):登錄 `0x53a79` chapter_dialog_table(FDTXT.DAT 第 章節+1 條,dialog `0x15f84` 的文字表),遊戲函式 532 / 1202、全域位址 14 / 900、資料 74 / 35714 bytes。下一批:`0x538a8` / `0x538b0`、`0x53a49`。
續一百九十八(2026-11-06):登錄 `0x538a8` ail_mix_src_end / `0x538b0` ail_mix_build_end(AIL 混音迴圈終點)與 `0x53a49` field_canvas(456 × 336 戰場離屏畫布),遊戲函式 575 / 1202、全域位址 17 / 900、資料 86 / 35714 bytes。下一批:`0x51a83`、`0x5030f` / `0x50311`、`0x53aa9` / `0x53aad`、`0x53c03`。
續一百九十九(2026-11-06):登錄 `0x51a83` target_range_selector(範圍框模式 0 .. 6 兼目標半徑 = 記錄 byte + 2),遊戲函式 587 / 1202、全域位址 18 / 900、資料 90 / 35714 bytes。下一批:`0x5030f` / `0x50311`、`0x53aa9` / `0x53aad`、`0x53c03`、`0x53c57`。
續二百(2026-11-06):登錄 `0x5030f` ail_debug_indent_space / `0x50311` ail_debug_indent_mark(AIL_DEBUG 記錄的 14 空白 + 深度 − 1 個 `0xFA` 縮排),遊戲函式 587 / 1202、全域位址 20 / 900、資料 94 / 35714 bytes。下一批:`0x53aa9` / `0x53aad`、`0x53c03`、`0x53c57`、`0x53beb`。
續二百零一(2026-11-06):登錄 `0x53aa9` camera_x / `0x53aad` camera_y(戰場鏡頭原點,格;畫面 13 × 8),遊戲函式 591 / 1202、全域位址 22 / 900、資料 102 / 35714 bytes。下一批:`0x53c03`、`0x53c57`、`0x53beb`、`0x53a7d`。
續二百零二(2026-11-06):登錄 `0x53c03` current_chapter(章節跳表 / 曲表 / FDFIELD 條目的索引,16 個過章 handler `inc`),遊戲函式 596 / 1202、全域位址 23 / 900、資料 106 / 35714 bytes。下一批:`0x53c57`、`0x53beb`、`0x53a7d`、`0x538b4` / `0x538b8`。
續二百零三(2026-11-07):登錄 `0x53c57` menu_cursor_index(43 個函式共用的選單游標 index),遊戲函式 598 / 1202、全域位址 24 / 900、資料 110 / 35714 bytes。下一批:`0x53beb`、`0x53a7d`、`0x538b4` / `0x538b8`、`0x53ad5`。
續二百零四(2026-11-07):登錄 `0x53beb` field_unit_count(單位陣列 `[0x53a45]` 的筆數),遊戲函式 612 / 1202、全域位址 25 / 900、資料 114 / 35714 bytes。下一批:`0x53a7d`、`0x538b4` / `0x538b8`、`0x53ad5`、`0x53a51`。
續二百零五(2026-11-07):登錄 `0x53a7d` resident_text_table(FDTXT.DAT 第 0 條,dialog 的常駐文字表),遊戲函式 612 / 1202、全域位址 26 / 900、資料 118 / 35714 bytes。
續二百零六(2026-11-07):登錄 `0x538b4` / `0x538b8` ail_resample_frac_step / ail_resample_int_step(AIL 重取樣的分數 / 整數步進),遊戲函式 648 / 1202、全域位址 28 / 900、資料 126 / 35714 bytes。
續二百零七(2026-11-07):登錄 `0x53ad5` battle_event_state_table(malloc(0x20) 的戰鬥事件狀態表指標),遊戲函式 659 / 1202、全域位址 29 / 900、資料 130 / 35714 bytes。
續二百零八(2026-11-07):登錄 `0x53a51` field_map_cells(FDFIELD.DAT 第 章節×3 條的地圖格緩衝),遊戲函式 659 / 1202、全域位址 30 / 900、資料 134 / 35714 bytes。下一批:`0x53bfb`、`0x53ab5`、`0x53bef`、`0x53ab1` / `0x53ab9`。
續二百零九(2026-11-07):登錄 `0x53bfb` roster_count(常駐名冊 `[0x53bf7]` 的人數),遊戲函式 661 / 1202、全域位址 31 / 900、資料 138 / 35714 bytes。
續二百一十(2026-11-07):登錄 `0x53ab5` cursor_cell_y(戰場游標 Y = 鏡頭 Y + 畫面內游標 Y),遊戲函式 661 / 1202、全域位址 32 / 900、資料 142 / 35714 bytes。
續二百一十一(2026-11-07):登錄 `0x53bef` turn_number(回合數,回合事件列的比對值),遊戲函式 668 / 1202、全域位址 33 / 900、資料 146 / 35714 bytes。
續二百一十二(2026-11-07):登錄 `0x53ab1` / `0x53ab9` cursor_cell_x / cursor_screen_x(戰場游標 X、畫面內游標 X),遊戲函式 673 / 1202、全域位址 35 / 900、資料 154 / 35714 bytes。下一批:`0x53abd`(26)、`0x51a4d` / `0x53a61` / `0x53a81`(26)、`0x53a55`(25)。
續二百一十三(2026-11-07):登錄 `0x53abd` cursor_screen_y(畫面內游標 Y),遊戲函式 678 / 1202、全域位址 36 / 900、資料 158 / 35714 bytes。
續二百一十四(2026-11-07):登錄 `0x51a4d` fdother_dat_filename、`0x53a61` fdicon_cache_buffer、`0x53a81` fdother_ui_container,遊戲函式 693 / 1202、全域位址 39 / 900、資料 178 / 35714 bytes。
續二百一十五(2026-11-07):登錄 `0x53a55` field_control_block(FDFIELD 控制段),遊戲函式 702 / 1202、全域位址 40 / 900、資料 182 / 35714 bytes。下一批:`0x53eec`(24)、`0x53ac1`(23)、`0x53ecc`(23)、`0x53bf7` / `0x53f66` / `0x541f4`(20)。
續二百一十六(2026-11-07):登錄 `0x53eec` ui_sfx_pool(FDOTHER 第 31 號 UI 音效池),遊戲函式 706 / 1202、全域位址 41 / 900、資料 186 / 35714 bytes。
續二百一十七(2026-11-07):登錄 `0x53ac1` field_map_width(戰場地圖寬),遊戲函式 711 / 1202、全域位址 42 / 900、資料 190 / 35714 bytes。
續二百一十八(2026-11-07):登錄 `0x53ecc` battle_end_code(戰鬥結束碼),遊戲函式 730 / 1202、全域位址 43 / 900、資料 194 / 35714 bytes。
續二百一十九(2026-11-07):登錄 `0x53bf7` roster_buffer、`0x53f66` town_menu_resource、`0x541f4` ail_error_text,遊戲函式 738 / 1202、全域位址 46 / 900、資料 458 / 35714 bytes。下一批:`0x53c5f` / `0x53c63` / `0x53ec8`(19)、`0x53ec4`(18)、`0x53a5d`(16)、`0x51a87`(15)。

**不再處理**:worklist 的 obsolete_remake 68 項 —— 屬於已移除的 remake;使用者 2026-11-05 決定不恢復 remake,這 68 項維持關閉。

## 2. 假設(影響結論的前提)

| 假設 | 依據 / 狀態 |
|---|---|
| DOSBox-X 的行為代表原版在 DOS 上的行為 | 所有「實機」都是 DOSBox-X 模擬,**沒有一項是真硬體驗證**;計時類結論(例如 delay 差 0.5%)已註明是 DOSBox-X Sound Blaster 的切片 |
| `docs/data/chapter_beats/chNN` 的 NN = 章節 byte `[0x53c03]` | ev_s193 的名冊下界刻意算到「錯一位也成立」;未逐檔核對 |
| `chapter_beats` 最外層的入隊 op 是無條件的 | ev_s193 另算「整個處理常式有任何條件 op 就不算」的保守下界 |

## 3. 已知問題

| 問題 | 現象 / 影響 | 處理 |
|---|---|---|
| 旗標章節(byte 22 / 23 / 24 / 27 / 28 / 29)選人無出口 | 名冊 − 1 < 目標(15 / 19)時 Esc 立刻再進選人;只有改過章節 byte 的存檔會遇到(lc192b、doc99 新卡點 A) | 原版行為,不改;測非正常存檔前先補名冊,或在 `0x2b0e3` 改 EBP(續一百九十二的做法) |
| pass-through mapper 綁 DOSBox-X binary | 預設綁定不同的 binary 用這個 map 會缺鍵 | harness 的 `mapper_guard` 只接受 `tools/dosbox/passthrough.map.binmd5` 列的 binary(現有兩支:491af5d1…、b3084f20…);新 binary 先 `make_passthrough_map.py attest --bin …`。`drivers_s191/lc191.py` 的部分 mapper 實驗沒有 sidecar,重跑會被擋(要刻意重做時設 `FD2_HARNESS_MAPPER_UNCHECKED=1`) |
| debugger 在 real mode 讀不到 selector 0170 | 讀取失敗 | `drivers_s192/lc192.py` 的 `halted()`:resume、等 0.4 s、重讀(續一百九十二 7 次都第 2 次成功) |
| CALLLOG 以 4 KiB 區塊寫出 | 執行中讀到的尾端會落後 | teardown 之後再算 md5 / 結論(續一百六十九、一百七十) |
| Git Bash 會改寫 `/home/...` 參數 | 傳給 WSL 的路徑變成 `C:/Program Files/Git/home/...` | 指令前加 `MSYS_NO_PATHCONV=1` |
| `~/fd2-run-harness-mt1`(WSL) | 續一百九十三第一版 mapper 測試的變異真的啟動過一次留下的工作目錄(假 binary、沒有遊戲) | 已處理:使用者 2026-11-05 要求刪除;刪前確認是空目錄(0 個檔案、非 symlink、無程序使用),以 `rmdir` 刪除 |

## 4. 主要決策(為什麼這樣做)

- 只用原版 EXE 當證據;remake 的輸出不算證據(98-index「證據來源判準」)。
- 每個結論都由 `evidence/generators/ev_*.py` 從原始輸入重算,assert 數由 `assert_census.py` 看守,每個產生器配 `mut_*.py` 變異測試(未變異對照必須與已提交檔相同)。
- 實機前先寫預測檔、一步一個呼叫(或 `&&`)、每個讀取都要有期望值會失敗;必要的記憶體修改先在預測檔寫理由(續一百九十二)。

## 5. 外部相依

- WSL `Ubuntu`:Xvfb、xdotool、tmux、python3;DOSBox-X 兩支 build —— `~/fd2-dosbox-calllog4/dosbox-x/src/dosbox-x`(呼叫紀錄修補版,md5 491af5d1…)
  與 `~/fd2-dosbox-build/dosbox-x/src/dosbox-x`(harness 預設,md5 b3084f20…)。
- Windows:Python 3.13、capstone 5.0.7。遊戲檔在 `FD2_GAME_DIR`(不進倉庫)。

## 6. 入口與例行檢查

| 用途 | 指令 |
|---|---|
| 待辦總數 | `python tools/worklist_checklist.py --summary`(另有 `--check`、`--selftest`) |
| 規格層覆蓋率 | `python tools/re_coverage.py`(摘要)、`--check`、`--gaps globals \| code \| data \| resources \| files`、`--show-data ADDR`、`--show-resource DAT IDX` |
| 證據全部重算 | `python docs/knowledge-base/evidence/generators/run_all.py` |
| assert 數量 | `python docs/knowledge-base/evidence/generators/assert_census.py`(`--executed` 動態) |
| 改過的工具 | `python tools/verify_selftest_discrimination.py --exhaustive --tool NAME.py`(不要用 `--precommit`) |
| 提交前閘門 | `re_coverage.py --check`、`verify_tool_hygiene.py`、`audit_evidence_provenance.py --gate` / `--diff`、`verify_address_citations.py --diff`、`verify_address_claim_coverage.py`、`doc98_index.py --check`、`git diff --check` |
| harness 離線測試(WSL) | `bash tools/test_dosbox_harness_ports.sh`、`bash tools/test_dosbox_harness_mapper.sh` |
| mapper | `python tools/dosbox/make_passthrough_map.py check` / `attest [--bin B]` / `--selftest` |

## 7. 需要人決定

1. ~~是否恢復 remake~~ —— 已決定(2026-11-05):不恢復;obsolete_remake 68 項維持關閉。
2. ~~`~/fd2-run-harness-mt1` 是否刪除~~ —— 已決定(2026-11-05):刪除,已完成(空目錄,`rmdir`)。
3. ~~下一個研究目標~~ —— 已決定(2026-11-05):規格層 100% 逆向,見 §1「進行中」。
