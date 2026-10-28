# 證據產生器

`docs/knowledge-base/evidence/` 的 57 份證據 JSON 都由本目錄的產生器從原始紀錄重算,
不是手寫的。產生器逐項 `assert` 判準與預測,任何一項不符就失敗。

## 續一百五十九(2026-10-28)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s159.py` | `copyprot_patch_record_s159_20261028.json` | `mut_s159.py`(30) |

第 6 項(防拷兩處無條件跳躍是誰改的):`FD2_APK/PASS.DAT` 是 MS-DOS COMP 的輸出,逐字解析後兩筆差異的檔案位移以兩個獨立的 LE 換算對回 0x118aa / 0x34233,
file1 = 參考版的 EB、file2 = 原版的 75 / 74;套回 file2 重建原版(md5、反組譯 jne / je)、對照續一百三十七反事實用的值;三份目錄快照的時間序與全 C 槽掃描。
第四段是第 5 項第 5 次實機(lc159a)在設定步驟 FAIL 的截圖判讀。驅動腳本、目錄快照腳本與量之前的預測在 [`drivers_s159/`](drivers_s159/README.md)。

## 續一百五十八(2026-10-27)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s158.py` | `followups_s158_20261027.json` | `mut_s158.py`(24) |

續一百五十七留下的項目。前三段離線,用續一百五十七的三份附指令數呼叫紀錄重算:第二輪擺法的鏡頭(地形層 96 格的地形索引對 33 張 FDFIELD 構成資源比對,
單位貼圖位置換回地圖座標,對照 `draw_unit_sprite` 的裁切);地形層多出的指令數(每個 (貼圖函式, 地形索引) 取最小指令數,照圖塊組合預測,同鏡頭兩份當對照);
BIOS tick 的 5 ms 格點(`wait_ticks` 返回時間的相位集中度,對照計時器 ISR 與 PIT 設定的程式碼)。第四段是第 5 項第 4 次實機(lc157f)的 FAIL 紀錄,
驅動腳本與量之前的預測在 [`drivers_s158/`](drivers_s158/README.md)。

## 續一百五十七(2026-10-27)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s157.py` | `live_items_s157_20261027.json` | `mut_s157.py`(30) |

續一百五十五列為「要實機」的 6 項裡有結果的 4 項(DOSBox-X,原版 FD2.EXE;原始紀錄 `.wsl_build/lc157_live/`,驅動腳本在 [`drivers_s157/`](drivers_s157/README.md)):
第 1 項灰階版 0x4e1a6 的模式 1(兩份 VGA 傾印 + `[0x53a61]` 單位圖快取,照 `draw_unit_sprite` 逐像素預測)、
第 3 項指令表第 1、2、5、7 格的入口(呼叫紀錄,`[0x53af9]` = 1 / 0 兩輪)、第 4 項索引 255 的 DAC(除錯器讀 DAC,對照 `ev_s145` 的 `fade6`)、
第 2 項光束炮相位迴圈 redraw 的內部時間(附指令數的呼叫紀錄三份,量之前的預測 P1 .. P5 逐項判定,P2 不成立)。
`ev_s145.py` 的 `fade6`、`ev_s132.py` 的 `judge` 都是從原始碼抽出那一個函式執行。

## 續一百五十六(2026-10-27)

`ev_lut_circle_ramp_at_unit` 的形狀判準改成逐像素的精確預測:換色段照 `remap_circle_scanlines`(0x219ad)寫
(列 cy − r < y < cy + r、段 [max(0, cx − hw), min(cx + hw, 0x138)),右端不含),換色表是 FDOTHER #3 第 i 項(`[0x53a6d]`);
排除框外每個像素都要等於預測。原本的邊緣容差(±1 方向、往內 3 格、0 .. 2)整段拿掉。另排除施法者那一格(游標格):
基準畫面的重畫在那裡貼了 FDOTHER #1 第 0 項(法術兩組)或以 byte3 換色畫成另一階(道具 79),逐像素檢查後才排除。
對照加「右端含 cx + hw」「換色表錯開一幀」兩個。證據的 `shape` 改欄位(`edge_rows` / `edge_ok` → `same_in` / `mismatch`),
多 `cursor_cell`、`cursor_cell_cause`、`remap_model`。

## 續一百五十五(2026-10-27)

`ev_lut_circle_ramp_at_unit` 的資訊框改由 `draw_map_hud`(0x1acf3)與 FDOTHER #5 第 130 格(69 × 34)定,x 位置在 `[0x51a0c]` 的兩個可能值裡
由「資源像素與基準畫面相同」選;單位格改成逐格比對 FDICON 單位圖(10 幀相同、施法者在裡面),與原本手寫的格相同。
證據只有 `excluded_rects` 改變;這一支多讀 FDICON.B24 與 FDOTHER.DAT(`inputs_manifest.json` 已登錄)。

## 續一百五十四(2026-10-27)

`ev_lut_circle_ramp_at_unit` 的單位排除框改用 `draw_unit_sprite` 的幾何(24 × 24、比格子上移 6 列,由 `_exeops.operand` 讀 FD2.EXE),
原本「24 × 36、往上 12」上下各多框 6 列;ai79 補上視窗下緣外 (1, 8) 的單位、施法者的格改由紀錄的 `unit_xy − scroll` 算。
證據 `lut_circle_ramp_at_unit_20261013.json` 因此改變(排除框變小、圓內像素變多,判準與對照照舊通過)。
`ev_item79_aim_exp_reward_lines` 的 `KEEP` 改由紀錄算(#6 照舊保留),證據逐 byte 不變。

## 續一百五十三(2026-10-24)

沒有新的證據檔。新增 `_exeops.py`:`operand(位址, 前綴, 後綴)` 讀 FD2.EXE 那一條指令的運算元(文字不符就 AssertionError)。
`ev_attack_exp`、`ev_level_up`、`ev_ai_spell_score`、`ev_terrain_modifier`、`ev_s66`、`ev_s67` 讀單位欄位(+5 / +7 / +8)的位移改由
遊戲裡讀寫同一欄位的指令取;`ev_heal_spell_targets` 的累加係數改由 heal_hp_apply 的指令與目標傾印算;`ev_s136` 加第二種寫法;
`ev_rest_and_item79_branch` 的 `KEEP` 改由紀錄算(道具使用者 + 被打到的單位)。sweep ESCAPED 16 → 2,證據逐 byte 不變;
`ev_attack_exp` / `ev_level_up` / `ev_terrain_modifier` 的 inputs_manifest 多記 FD2.EXE。

## 續一百五十二(2026-10-24)

沒有新的證據檔。`ev_s75` / `ev_s76` 的 `sweep_literals` 逃過項補判準(21 + 11 → 0):選擇器改由 LOGL 追蹤 / 受控注入的傾印鍵取,
描述子 base 以「追蹤裡的指令位元組 = 事前傾印在 base + EIP 的位元組」核對,#GP 向量由 DOSBox-X 記錄檔取,
INT 6 迴圈改由熱點次數的最大落差分組。兩份證據逐 byte 不變。

## 續一百五十一(2026-10-23)

沒有新的證據檔。`sweep_literals` 逃過的常數逐一補判準:續一百五十跑不完的 2 個(`ev_s73` 堆積走訪逐步斷言對齊與大小、
`ev_s139` 幀尺寸上限 320 × 200),與 10-06 那批、移植產生器共 34 個產生器(見 doc98 續一百五十一的表)。
判準來源:EXE 指令運算元、`docs/data/exe_tables/`(dump_exe_tables 另外抽)、FDFIELD(parse_field)、`function_inventory`、
攻守 / 相鄰 / 說明文字的交叉;另把輸出與斷言共用同一個變數、索引改解包、鍵名寫的位移由鍵名取值。
`ev_lut_circle_ramp_at_unit` 的 ai79 拿掉 3 個框內沒有換色的排除框(證據只有 `excluded_rects` 8 → 5)。

## 續一百五十(2026-10-23)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s150.py` | `palette_fade_index255_emulated_s150_20261023.json` | `mut_s150.py`(13) |

模擬,沒有執行遊戲:`x86_pal_emu.py`(極小的 x86-32 直譯器,capstone 解碼)直接執行原版 FD2.EXE 的 0x2df01 / 0x11df2 / 0x11d40,
記錄 `out 0x3c8 / 0x3c9`,對照 `ev_s145.py` 的 `fade6`(從原始碼抽出執行)。`mut_s150.py` 有 4 個變異改直譯器本身。
同一輪 `ev_s130.py`(T 行週期、迴圈外推進規則、直方圖合計、對照不符項)與 `ev_s131.py`(對照不符項)補 sweep 逃過的 13 個。

## 續一百四十五(2026-10-21)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s145.py` | `afterlock_live_title_transition_s145_20261021.json` | `mut_s145.py`(47) |

原版 FD2.EXE 開場「金鎖之後」到主選單靜止的 DOSBox-X 連拍 444 張(`.wsl_build/s145_afterlock/`);連拍腳本在 [`drivers_s145/`](drivers_s145/README.md)。
續一百四十七為 sweep 逃過的常數補判準:撕裂幀改在主機列判讀(恰好一組相鄰 dy)、淡入淡出的候選圖改成捲動緩衝的每一個 dy。
續一百四十八補 0x2df01 逐索引重算(每條主機列 = 某一步或 DAC 寫到一半,對照改向下取整)、logo 末幀 → 白(0x11df2)、選單文字整張比對(項數讀連拍目錄歸檔的 `FD2.SAV`)。
續一百四十九補 sweep 逃過的 20 個:讀 EXE 立即值一律從指令起點讀並驗 opcode(`imm`)、主機列數改由結果算、分段起訖 / 選單組合數 / 方框外框加斷言。

## 續一百四十一(2026-10-21)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s141.py` | `demonface_live_vs_fdother_scroll_s141_20261021.json` | `mut_s141.py`(41) |

續一百四十二更正並加強 `ev_s141.py`(黑幕後是 ANI #0 金鎖插播;絕對調色盤判準;觸發常數讀原版 FD2.EXE),證據檔同名重算。
續一百四十六為 sweep 逃過的常數補判準:實拍改以主機列解析度比對(水平兩點斷言相同)、FDOTHER 解碼與 `tools/decode_sprite.py` 對照。
連拍腳本在 [`drivers_s141/`](drivers_s141/README.md)。

## 續一百三十九(2026-10-21)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s139.py` | `rle4_roundtrip_s139_20261020.json` | `mut_s139.py`(27) |

## 續一百三十七(2026-10-20)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s137.py` | `remaining_items_offline_20261020.json` | `mut_s137.py`(39) |
| `ev_s138.py` | `remaining_items_offline_s138_20261020.json` | `mut_s138.py`(31) |

## 續一百三十六(2026-10-19)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s136.py` | `move_range_highlight_scope_20261019.json` | `mut_s136.py`(29) |

## 續一百三十五(2026-10-19)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s135.py` | `fdicon_mode1_vga_frames_20261019.json` | `mut_s135.py`(24) |

續一百 ~ 一百三十三在 DOSBox-X / WSL 上用過的驅動腳本(40 個)與 lc122 ~ lc131 的執行紀錄(23 份)在
[`drivers_s100_s133/`](drivers_s100_s133/README.md)。

## 續一百三十四(2026-10-17)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s134.py` | `fdicon_mode1_order_map_units_20261017.json` | `mut_s134.py`(24) |

續一百二十二 ~ 一百二十九的 8 份證據原本由暫存腳本產生,續一百三十四移進來(重算與已提交檔逐 byte 相同):

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_lut_circle_ramp_at_unit.py` | `lut_circle_ramp_at_unit_20261013.json` | `mut_lut_circle_ramp_at_unit.py`(13) |
| `ev_ai_item_action_item79_flow.py` | `ai_item_action_item79_flow_20261013.json` | `mut_ai_item_action_item79_flow.py`(17) |
| `ev_rest_and_item79_branch.py` | `rest_and_item79_branch_20261014.json` | `mut_rest_and_item79_branch.py`(16) |
| `ev_item79_aim_exp_reward_lines.py` | `item79_aim_exp_reward_lines_20261014.json` | `mut_item79_aim_exp_reward_lines.py`(11) |
| `ev_lut_circle_ramp_frame_time_ch22_post.py` | `lut_circle_ramp_frame_time_ch22_post_20261015.json` | `mut_lut_circle_ramp_frame_time_ch22_post.py`(12) |
| `ev_lut_ch22_post_cycles2500_chapter_tables.py` | `lut_ch22_post_cycles2500_chapter_tables_20261015.json` | `mut_lut_ch22_post_cycles2500_chapter_tables.py`(13) |
| `ev_dispatch_index_bounds_table_split.py` | `dispatch_index_bounds_table_split_20261015.json` | `mut_dispatch_index_bounds_table_split.py`(12) |
| `ev_cmd_table_0_9_coverage_lut_cycles.py` | `cmd_table_0_9_coverage_lut_cycles_20261016.json` | `mut_cmd_table_0_9_coverage_lut_cycles.py`(11) |

## 續一百三十三(2026-10-17)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s133.py` | `hud_icon_hp_digits_20261017.json` | `mut_s133.py`(23) |

## 續一百三十二(2026-10-17)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s132.py` | `phase_loop_runB_hud_icon_20261017.json` | `mut_s132.py`(20) |

## 續一百三十一(2026-10-17)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s131.py` | `move_range_remap_buffer_20261017.json` | `mut_s131.py`(20) |

## 續一百三十(2026-10-16)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s130.py` | `phase_loop_no_breakpoint_calllog_20261016.json` | `mut_s130.py`(24) |

## 續六十五~七十七(2026-10-01~10-05)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_s65.py` | `collect_targets_selector_20261001.json`、`terrain_shipped_maps_20261001.json` | — |
| `ev_s65b.py` | `terrain_events_map_attack_20261001.json` | — |
| `ev_s66.py` | `ai_mode8_move_confirm_boss_20261001.json` | — |
| `ev_s67.py` | `path_search_hits_friendly_mode8_20261001.json` | — |
| `ev_s68.py` | `ai_seek_opponent_rand_trace_20261001.json` | — |
| `ev_s69.py` | `offmap_unit_event_camera_trace_20261001.json` | — |
| `ev_s70.py` | `offmap_event0_roster_heap_20261002.json` | — |
| `ev_s71.py` | `offmap_event0_followups_20261002.json` | — |
| `ev_s72.py` | `garble_portrait_heap_null_speaker_20261002.json` | — |
| `ev_s73.py` | `speaker_lookup_title_palette_heap_walk_20261002.json` | — |
| `ev_s74.py` | `runaway_blit_exit_frees_fake_node_title_reload_20261003.json` | `mut_s74.py`(8) |
| `ev_s75.py` | `runaway_blit_triple_fault_continue_load_control_20261005.json` | `mut_s75.py`(10) |
| `ev_s76.py` | `runaway_blit_fault_class_dos16m_guard_20261005.json` | `mut_s76.py`(19) |

## 續四十六~六十四(2026-09-29~10-01)

| 產生器 | 證據檔 | 變異測試 |
|---|---|---|
| `ev_ai_action_choice.py` | `ai_action_choice_20260930.json` | — |
| `ev_ai_heal_score.py` | `ai_heal_score_20260930.json` | — |
| `ev_ai_item_score.py` | `ai_item_score_20260930.json` | — |
| `ev_ai_move_nearest.py` | `ai_move_nearest_20260930.json` | — |
| `ev_ai_physical_candidate.py` | `ai_physical_candidate_20260930.json` | `mut_ai_physical_candidate.py`(7) |
| `ev_ai_physical_untested_branches.py` | `ai_physical_untested_branches_20261001.json` | `mut_ai_physical_untested_branches.py`(11) |
| `ev_ai_spell_path.py` | `ai_spell_path_20260929.json` | — |
| `ev_ai_spell_score.py` | `ai_spell_score_20260930.json` | — |
| `ev_attack_exp.py` | `attack_exp_20260929.json` | — |
| `ev_attack_path_selection.py` | `attack_path_selection_20260929.json` | `mut_terrain_rules.py`(4) |
| `ev_collect_targets_in_range.py` | `collect_targets_in_range_20260929.json` | — |
| `ev_heal_spell_targets.py` | `heal_spell_targets_20260929.json` | — |
| `ev_level_up.py` | `level_up_20260929.json` | — |
| `ev_move_landing_select.py` | `move_landing_select_20260930.json` | — |
| `ev_real_kill_corpse.py` | `real_kill_corpse_20260930.json` | — |
| `ev_rest_recover.py` | `rest_recover_20260930.json` | — |
| `ev_spell9_path.py` | `spell9_path_20260930.json` | — |
| `ev_terrain_modifier.py` | `terrain_modifier_20260929.json` | `mut_terrain_rules.py`(7) |
| `ev_terrain_types_3_5.py` | `terrain_types_3_5_20260930.json` | — |

這批原本的腳本後段還會更新 `docs/data/function_names.json`(一次性補丁,當時已套用並提交);
移植時刪掉那一段,產生器只重算證據,不會改登錄檔。
`ev_ai_physical_candidate` / `ev_ai_physical_untested_branches` 原本只把分析結果搬進 JSON、沒有判準,
移植時補上(每次呼叫的列舉、逐組分數、每次比較後的全域、迴圈結束值都要與重算相符;每條對照規則至少在一組上不同),
變異測試把分析模組裡的規則逐條換成對照規則,每一個都讓產生器以 AssertionError 失敗。

## 執行

```
python run_all.py              # 全部重算到暫存目錄,與已提交檔案逐 byte 比對;全部 IDENTICAL 才 exit 0
python run_all.py ev_s76       # 只跑一個
python run_all.py --selftest   # 比對器與輸入檢查的正反對照
python mut_s76.py              # 變異測試:先跑未變異對照,再逐一跑每個變異(都要以 AssertionError 失敗)
python rebuild_excerpts.py     # 從 WSL 裡的完整記錄重切摘錄,與清單逐 byte 比對(掃描約 30 GB)
python rebuild_excerpts.py --from-backup <備份夾>   # WSL 裡的記錄不在時:從壓縮備份還原、驗 sha256 後重切
python rebuild_excerpts.py --selftest --from-backup <備份夾>   # 反向對照;WSL 沒有 v21 記錄又沒給備份夾時回報 BLOCKED(rc 2)
python sweep_literals.py [ev_s65b ...]   # 每個數字常數 +1 重算:找出寫進證據卻沒有判準擋得住的手寫值
python assert_census.py                 # 每個產生器的 assert 個數與 assert_census.json 比:變少 / 沒更新基準都 exit 1(秒級,提交前跑)
python assert_census.py --executed      # 重算產生器,記下沒執行到的 assert;執行到的個數變少就 exit 1
python assert_census.py --update [--executed]   # 刻意增刪 assert 後重寫基準(提交訊息說明原因)
python assert_census.py --selftest
python sweep_literals.py --selftest
```

`run_all.py` 與變異測試都不會覆寫已提交的證據檔。要更新證據時才直接執行產生器(`python ev_s76.py`),
它會寫到 `docs/knowledge-base/evidence/`。新增產生器時加進 `build_manifest.py` 的 `GENERATORS`,
再執行 `python build_manifest.py <名稱>`(只重錄指定的那幾個)。

## 輸入不在 git 裡

產生器讀的原始紀錄(`.wsl_build/` 的 DOSBox-X 傾印、追蹤、截圖與記錄檔)、
`extracted/` 與原版遊戲檔(`org_game/`,可用 `FD2_GAME_DIR` 指到別處)都被 `.gitignore` 排除:
原版程式與資產受著作權保護(見倉庫 `README.md`),記憶體傾印裡有原版程式與資料。

所以每個產生器啟動時先呼叫 `_evpaths.require_inputs()`,依 `inputs_manifest.json` 比對每一筆輸入的
大小與 sha256;缺檔或內容不同時以 exit code 3 結束並列出每一筆(`run_all.py` 顯示為 `MISSING_INPUT`)。
在沒有這些原始紀錄的機器上,結果是 `MISSING_INPUT`,不是一份算錯的證據。

`inputs_manifest.json` 由 `build_manifest.py` 產生(以 `_trace/sitecustomize.py` 的 audit hook 記錄實際開啟的檔案,
子程序也記);只有原始紀錄確實換過時才重建。已追蹤的檔案不列入清單,改動後由 `run_all.py` 的逐 byte 比對發現。

## 終端輸出與摘錄

- **終端輸出**:續四十六~六十四的驅動腳本把斷點停點的暫存器讀值印到終端,沒有另存檔案。這些輸出從 Claude Code
  對話紀錄(`toolUseResult.stdout`)原樣匯出到 `.wsl_build/ctr/console/<UTC 時間>_<tool_use_id>.txt`,旁邊的
  `.meta.json` 記錄當時的指令、說明與時間;和其他原始紀錄一樣由清單以 sha256 鎖定。12 個產生器
  (`ev_ai_action_choice`、`ev_ai_heal_score`、`ev_ai_item_score`、`ev_ai_spell_path`、`ev_ai_spell_score`、
  `ev_attack_exp`、`ev_attack_path_selection`、`ev_level_up`、`ev_rest_recover`、`ev_spell9_path`、
  `ev_terrain_modifier`、`ev_terrain_types_3_5`)原本把這些讀值抄寫在程式裡,現在經 `_console.py` 解析;
  換之前逐值比對,解析值等於原抄寫值;並加上交叉檢查:同一段終端輸出印出的其他欄位(攻擊後 EX、HP、座標等)
  必須等於同一案例的傾印,證明那段輸出與那份傾印是同一次執行,不是只靠順序對上。
  `mut_console_level_terrain.py`、`mut_console_spell_path.py`、`mut_console_ai_score.py`、`mut_console_action_rest.py`
  在記憶體中竄改終端文字或交換案例段落(共 40 個變異),每一個都要讓產生器以 AssertionError 失敗。
  `tx_console.py` 負責 DOSBox-X 終端輸出的匯出與再驗證:`check --transcript <對話紀錄>` 對每份 `.txt` 在對話紀錄裡找同一個
  tool_use_id,要求 stdout 逐 byte 相同、`.meta.json` 的指令 / 說明 / 時間 / stderr 也相同
  (同一 id 有多筆結果紀錄時只取非空的,非空的必須彼此相同);`export <id> ...` 只寫新檔,遇到內容不同的既有檔就失敗;
  `extract` 把這些 id(另可加 id)在對話紀錄裡的原始紀錄行原樣抽成 `.jsonl.xz`,對話紀錄被清掉後
  `check --transcript <抽出檔>` 仍可比對。2026-10-06:對原始對話紀錄與抽出檔各跑一次,59/59 IDENTICAL;
  複製 console 目錄後改一個 byte、改一份 meta 的說明,分別判為 DIFFERENT、META_DIFFERENT(exit 1);
  `--selftest` 以合成紀錄涵蓋全部判定。
- **摘錄**:幾個輸入是從 WSL 裡的大型記錄(`~/fd2-run-harness-<run>/LOGCPU.TXT` 每份約 5 GB、`dosbox-x.log`)
  切出的摘錄(`exc_entries`、`stos_writes`、`trace_excerpt`、`post_reset_trace`、`post_reset_messages`、
  `guard_reentry_lines`、v33 的 `dosbox-x_log_excerpt`)。`python rebuild_excerpts.py` 依當時的切法從完整記錄
  重切到 stdout,與清單逐 byte 比對(只讀記錄檔,不啟動 DOSBox-X);`--selftest` 是反向對照。
  完整記錄不在時回報 `SOURCE_MISSING`,大小與程式裡的 `SOURCE_LOGS` 不符(例如被新的執行覆寫)時回報 `SOURCE_CHANGED`。
  6 份完整記錄(5 份 LOGCPU.TXT、v33 的 dosbox-x.log,約 27 GB)另以 xz 壓縮備份在倉庫外的本機備份夾
  (`fd2_re_evidence_raw_backup/full_logs_20261005/`,約 134 MB,`full_logs_manifest.tsv` 記大小與 sha256;
  備份時逐份解壓比對)。WSL 裡的記錄不在時改用 `python rebuild_excerpts.py --from-backup <備份夾>`:解壓到 WSL 暫存目錄、
  逐份以 `SOURCE_LOGS` 驗 sha256,再用同一組切法重切,結束後刪除暫存目錄。v21 的大小與 sha256 另與 `trace_excerpt.txt`
  切出當時印下的值相同。**2026-10-08 起 WSL 裡的完整記錄已刪除**:不給 `--from-backup` 時 7 個都是 `SOURCE_MISSING`,
  `--selftest` 也要加 `--from-backup <備份夾>`(正向對照「原樣 → IDENTICAL」需要真的 v21 記錄)。

## 手寫值掃描(`sweep_literals.py`)

`IDENTICAL` 只證明可重現。寫進證據、卻不影響任何 DOSBox-X 實測結果的手寫值,錯了也不會被發現(例:`ev_attack_path_selection` 的
`attacker_terrain_mod`)。`sweep_literals.py` 把產生器裡每個數字常數 +1 重算:以 AssertionError 失敗是 `KILLED`(有判準),
成功但輸出不同是 `ESCAPED`(寫進證據卻沒有判準);`ESCAPED` 再依語法位置分組,`data`(只經 dict / list 就寫出的手寫資料)
是要逐筆看的那一組。`--selftest` 檢查改寫位置、判定器、語法分組,並在 `ev_s65b` 把一個算出的欄位換回等值手寫常數,
確認它被點名。

2026-10-06 全部 32 個產生器掃一遍:`data` 組 251 個常數(98 行)。逐行對照輸入,**沒有值是錯的**,但有這些缺口,已補:

- `ev_s67` 對結論(泛洪 / 路徑搜尋逐格相同、打幾下等於預測、模擬器變異被擋下)完全沒有斷言,現在都有。
- `ev_heal_spell_targets` 的亂數 `roll`(斷點 0x1c971 的 EDX)與 `ev_real_kill_corpse` 的死亡旗標寫入點沒有存檔;當時的終端輸出
  從對話紀錄匯出到 `.wsl_build/ctr/console/`(5 份),改為解析並與傾印交叉比對。
- 法術 / 道具列、會心門檻、地形修正表原本手抄:改從 FD2.EXE 或執行期傾印讀。
- 多數 `data` 常數是把已經斷言過的值再手寫一次(斷言只管住其中一份):改成引用同一個變數或計算式。
- `ev_s76` 的 IDT 檢查對所有向量都成立(全是 0070 / 0x8e):改比向量 8 的閘入口與記錄裡計時器出差的入口;`GDT_DUMP` 加
  「前緣之後事後傾印與事前相同」。
- `ev_terrain_types_3_5` 自己有一份地形規則:改用 `_terrain.py`。

修正後 `data` 組剩 18 個,全是實驗設定(`TIE_ACTOR`、`ev_s76` 選來展示的向量 / 選擇器、截圖裁切框)、迴圈計數器,
以及兩個資料本身分不出來的值:`ev_heal_spell_targets` 的經驗值係數 40 / 36 / 32(取自 doc98 續四十七,規則未明)、
`ev_real_kill_corpse` 0x1dc61 那列的回合(#7 在第 1、2 回合都被重寫)。`KILLED` 1596 → 1857。

2026-10-19(續一百三十五)判定器改正:原本只看 stderr 最後一行是不是 `AssertionError`,`assert x, 多行字串` 會被判成 CRASH。
現在產生器以 sitecustomize 包住 `sys.excepthook`,在 stderr 補一行 `__SWEEP_FINAL_EXC__ <型別>`,判定看最後一個標記
(只裝在產生器本身,它再開的子行程不受影響)。另修了對照失敗那一筆的欄位錯位(印出時崩潰)。移植的 7 個產生器與分析模組都掃過,
逃過項的處理見 doc98 續一百三十五。

略過的關鍵字參數(`SKIP_KEYWORDS`):`indent`,以及 `ndigits`(續一百四十六)—— 只有寫成 `round(x, ndigits=N)` 才略過,位置參數 `round(x, N)` 照樣變異。

## 限制

- `IDENTICAL` 證明可重現,不證明正確;正確性由產生器裡的 `assert` 與變異測試負責。
- 原始紀錄只有倉庫外同一顆硬碟上的本機備份(`fd2_re_evidence_raw_backup/`,最新一份 `evidence_inputs_all_20261021d.tar.xz`
  含清單上全部 3178 個非遊戲檔,遊戲檔在 `*_20261005b`),沒有第二份;硬碟損壞時產生器全部變成 `MISSING_INPUT`。
- 終端輸出的原始來源是 Claude Code 對話紀錄(本機 `~/.claude/projects/` 下約 1.7 GB 的 jsonl),可能被 Claude Code 依保留期限清除。
  同一備份夾的 `transcript_records_20261006.jsonl.xz`(旁有 `.sha256`)保留 86 個 id 的 291 行原始紀錄:
  59 份終端輸出,加上切出摘錄的 27 個指令(`rebuild_excerpts.py` 的切法出處);只能證明匯出與紀錄一致,
  不能證明紀錄之後沒有被改過。抽出檔含原版程式的讀值,不進 git。
- `ev_s68`、`ev_s69` 以子行程執行 `an_f.py` / `an_ev.py`,每次都把 `f_calls.json` / `e2_lookup_rows.json` 重寫回 `.wsl_build/`
  (內容相同);其他產生器已改為直接呼叫分析模組。
- 證據裡的檔案路徑一律經 `_evpaths.rel()` 寫成 `/` 分隔(遊戲目錄內的檔案記成預設位置
  `org_game/炎龍騎士團/FLAME2/…`,身分由旁邊的 md5 鎖定),不隨作業系統或 `FD2_GAME_DIR` 改變;
  `run_all.py --selftest` 的第 5 個對照把遊戲目錄放到倉庫外重算。
- `ev_ai_physical_untested_branches` 記錄的是 2026-10-01 當時 `docs/data/exe_tables/native_movement_cost_rows.json`
  每列錯一個 byte 的狀態(ae1ff0f3 已修正),所以 `tr_analyze.py` 以 `_evpaths.git_blob()` 讀當時的 blob,
  不讀工作樹;讀不到(例如淺層 clone)時 exit 3。
- `ev_level_up`:13:40 那次 `dlg_step.sh LB 2` 的標籤寫錯(程式裡的 `ALIAS` 把它歸到 LA),歸屬由 DOSBox-X 斷點輸出內容確認:
  沒有攻擊停點;唯一的成長停點是 `unit+0x46`(MaxMP),不是新一次升級的開頭 `unit+0x37`;成長列指標與訊息序號
  接續 LA 前一段;`post_LA.bin` 的 MaxMP 增量等於它。`mut_console_level_terrain.py` 模擬「其實是另一次升級」的
  兩種輸出(從 `unit+0x37` 開始、含攻擊停點),都會被擋下。
- `ev_attack_path_selection` 的 `hits` 表:攻守雙方由停點、AP / DP 由攻擊前傾印把關;地形修正由 M3 同一指令傾印的
  地圖格 `m_map3.bin`(與地形測試的 `t_map.bin` 逐 byte 相同)依 `_terrain.py` 的規則算出,並比對那次終端輸出
  印出的地形類型。只有 M3 的 DOSBox-X HP 實測能區分有無地形修正(產生器以對照斷言);M1、M2 與 null(跳過)欄位是規則的
  套用,規則本身由 `ev_terrain_modifier` 的斷點讀值驗證(`mut_terrain_rules.py`)。M1~M3 出手與被打的單位都站在類型 0,
  「攻方修正看守方的格子」這種錯在這份資料上分不出來,所以「哪一方看哪一格」寫在兩者共用的 `_terrain.exchange()`,
  由 `ev_terrain_modifier` 的 T3~T5、T7(攻守雙方站在不同類型)擋下。原本手寫的表把 3 擊的
  `attacker_terrain_mod` 記成 0(索爾種族 5,應為 null;傷害不受影響),已更正。

## 其他腳本

- 共用模組:`_evpaths.py`(路徑、輸入檢查、`rel()`、`git_blob()`)、`_console.py`(終端輸出)、`_mutrun.py`(變異測試)、
  `_terrain.py`(地形修正規則,`ev_terrain_modifier` 與 `ev_attack_path_selection` 共用)、
  `_fields.py`(鍵名寫的位移 = 讀值的位移,`ev_s70` 用)。
- `tx_console.py`:終端輸出與對話紀錄的匯出、比對、抽出(見「終端輸出與摘錄」);取代當時在 scratchpad 的
  `tx_index.py` / `tx_export.py`。
- 輔助模組(產生器會匯入或執行):`an_f.py`、`an_ev.py`、`live.py`、`rng.py`、`sim_path.py`、`sim_dialog.py`、
  `dato_match.py`、`walk_after.py`;分析模組 `pa_analyze.py`、`tr_analyze.py`、`sl_analyze.py`、`sel_analyze.py`
  (原本把結果寫成 `.wsl_build` 裡的 `analyze*.json` 再由證據腳本讀回,現在產生器直接呼叫重算)。
- 續一百二十二 ~ 一百二十九的分析與內層突變模組(續一百三十四從暫存移進來,只改路徑與載入方式):`lc124_analyze.py` / `lc124_mut.py`、
  `lc125_analyze.py` / `lc125_mut.py`、`lc126_analyze.py` / `lc126_mut.py`、`lc127_analyze.py` / `lc127_mut.py`、
  `lc128_analyze.py` / `lc128_mut_image.py` / `lc128_mut_tool.py`、`lc129_analyze.py` / `lc129t_analyze.py` / `lc129_mut.py`。
  產生器以子行程重跑內層突變,輸出原樣寫進證據。拼接圖由傾印重畫後與已提交的 PNG 逐像素比對(文字標籤不比)。
- `_blobtools.py`:從 git blob 載入當時那一版的 `tools/verify_event_dispatch_table.py` 與 `docs/data/live_exec_addresses.json`
  (續一百二十八 / 一百二十九的證據依賴它們;之後改了這兩個檔,證據仍照當時的版本重算)。
- 驅動腳本存檔:當時在 DOSBox-X 上產生原始紀錄的腳本,檔頭標了「存檔」,路徑保留當時的工作環境,不保證能直接執行;
  只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)使用。
  - 續六十五~七十七:`t_v*.py`、`*_setup.py`、`mk_t_v*.py`、`reach_battle.py`、`inj_s77.py`、`v21_*.sh` 等;
    證據 JSON 的 `drivers` 欄位指向這裡。
  - 續四十六~六十四(依各檔標頭說明與輸出路徑歸類,未逐一重跑):
    通用斷點記錄 `bp_log.sh`、`bp_loop.sh`、`dlg_step.sh`;
    單次攻擊 / 施法受控測試 `exp_test.sh`、`lvl_test.sh`、`terr_test.sh`、`spell_cast.sh`;
    `dump_collect.sh` + `collect_check.py`(collect_targets_in_range)、`sel_setup.sh`、`sel_dump.sh`(`ev_s65` 的 selector);
    `mix_setup.sh`(ai_action_choice)、`it_setup.sh`(ai_item_score)、`mv_setup.sh`(ai_move_nearest)、
    `sc_setup.sh`(ai_spell_score)、`rg_setup.sh`、`rg_setup2.sh`(rest_recover)、`kc_setup.sh`(real_kill_corpse)、
    `s9_setup.sh`(spell9_path);`pa_setup.sh`、`pa_setup2.sh`、`pa_log.sh`(ai_physical_candidate);
    `tr_setup.sh`、`tr_setup2.sh`、`tr_setup3.sh`、`tr_log.sh`(ai_physical_untested_branches);
    `sl_setup.sh`、`sl_tie_setup.sh`、`sl_log.sh`(move_landing_select);
    終端輸出裡的記錄腳本 `sc_log.sh`(ai_spell_score)、`hl_setup.sh` + `hl_gen.py`(ai_heal_score)、`it_log.sh`(ai_item_score)、
    `mix_log.sh`(ai_action_choice)、`rg_log.sh`(rest_recover)、`s9_log.sh`(spell9_path)、
    `run_case.sh`、`lvl_print.py`(level_up)、`units_print.py`(傾印欄位列印)。
  - 2026-10-06 補收:當時在 DOSBox-X 上用過、但原本沒收進來的腳本(由對話紀錄裡每次 Bash 呼叫的指令比對出來):
    `kc_log.sh`(real_kill_corpse)、`mv_log.sh`(ai_move_nearest)、`sc_exp.sh`(ai_spell_score)、`hl_recompute.py`(ai_heal_score)、
    `collect_check.py`(`dump_collect.sh` 呼叫)、`hl_gen.py`(`hl_setup.sh` 呼叫);續六十五的 `terr_dump.sh`、`terr_attack.sh`、
    `map_atk.sh`、`phase_log.sh`、`ev_state.sh`、`skip_turn.sh`、`end_turn_once.sh`、`terrain_map.py`、`names_terrain.py`;
    續六十六的 `mode8.py`、`tp_step.py`;續六十八~六十九的 `v5_setup.py`、`v7_setup.py`、`t_ev.py`、`t_hang.py`。
  - 2026-10-06 靜態檢查(沒有在 DOSBox-X 上重跑):55 個 `.sh` 過 `bash -n`;37 個 `.py` 驅動可解析、沒有未定義名稱、
    匯入的模組都找得到;用到的 `tools/fd2_dosbox_live_helper.py` 子命令(`mem dump`、`mem read-global`、`debugger-cmd`、
    `key`、`resume` 等)與旗標都還存在;腳本與證據 JSON 提到的每個 `.py` / `.sh` 都在本目錄或 `tools/`。
    腳本裡指向 scratchpad 的路徑(`S=…/scratchpad`)照原樣保留,重跑前要改成本目錄。
