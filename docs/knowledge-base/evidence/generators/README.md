# 證據產生器

`docs/knowledge-base/evidence/` 的 33 份證據 JSON 都由本目錄的產生器從原始紀錄重算,
不是手寫的。產生器逐項 `assert` 判準與預測,任何一項不符就失敗。

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
| `ev_attack_path_selection.py` | `attack_path_selection_20260929.json` | — |
| `ev_collect_targets_in_range.py` | `collect_targets_in_range_20260929.json` | — |
| `ev_heal_spell_targets.py` | `heal_spell_targets_20260929.json` | — |
| `ev_level_up.py` | `level_up_20260929.json` | — |
| `ev_move_landing_select.py` | `move_landing_select_20260930.json` | — |
| `ev_real_kill_corpse.py` | `real_kill_corpse_20260930.json` | — |
| `ev_rest_recover.py` | `rest_recover_20260930.json` | — |
| `ev_spell9_path.py` | `spell9_path_20260930.json` | — |
| `ev_terrain_modifier.py` | `terrain_modifier_20260929.json` | — |
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
  在記憶體中竄改終端文字或交換案例段落(共 38 個變異),每一個都要讓產生器以 AssertionError 失敗。
- **摘錄**:幾個輸入是從 WSL 裡的大型記錄(`~/fd2-run-harness-<run>/LOGCPU.TXT` 每份約 5 GB、`dosbox-x.log`)
  切出的摘錄(`exc_entries`、`stos_writes`、`trace_excerpt`、`post_reset_trace`、`post_reset_messages`、
  `guard_reentry_lines`、v33 的 `dosbox-x_log_excerpt`)。`python rebuild_excerpts.py` 依當時的切法從完整記錄
  重切到 stdout,與清單逐 byte 比對(只讀記錄檔,不啟動 DOSBox-X);`--selftest` 是反向對照。
  完整記錄不在時回報 `SOURCE_MISSING`。

## 限制

- `IDENTICAL` 證明可重現,不證明正確;正確性由產生器裡的 `assert` 與變異測試負責。
- 證據裡的檔案路徑一律經 `_evpaths.rel()` 寫成 `/` 分隔(遊戲目錄內的檔案記成預設位置
  `org_game/炎龍騎士團/FLAME2/…`,身分由旁邊的 md5 鎖定),不隨作業系統或 `FD2_GAME_DIR` 改變;
  `run_all.py --selftest` 的第 5 個對照把遊戲目錄放到倉庫外重算。
- `ev_ai_physical_untested_branches` 記錄的是 2026-10-01 當時 `docs/data/exe_tables/native_movement_cost_rows.json`
  每列錯一個 byte 的狀態(ae1ff0f3 已修正),所以 `tr_analyze.py` 以 `_evpaths.git_blob()` 讀當時的 blob,
  不讀工作樹;讀不到(例如淺層 clone)時 exit 3。
- `ev_level_up`:13:40 那次 `dlg_step.sh LB 2` 依時間與 `post_LA.bin` 的寫入時間歸到 LA 對話的最後兩步
  (程式裡的 `ALIAS`),另以「5 個屬性指標各出現一次」把關;這是推論,指令本身沒有寫明。
- `ev_attack_path_selection` 的 `hits` 表:攻守雙方由停點、AP / DP 由攻擊前傾印把關;地形修正是依 doc 規則
  手算的預測,不由傾印讀出。

## 其他腳本

- 共用模組:`_evpaths.py`(路徑、輸入檢查、`rel()`、`git_blob()`)、`_console.py`(終端輸出)、`_mutrun.py`(變異測試)。
- 輔助模組(產生器會匯入或執行):`an_f.py`、`an_ev.py`、`live.py`、`rng.py`、`sim_path.py`、`sim_dialog.py`、
  `dato_match.py`、`walk_after.py`;分析模組 `pa_analyze.py`、`tr_analyze.py`、`sl_analyze.py`、`sel_analyze.py`
  (原本把結果寫成 `.wsl_build` 裡的 `analyze*.json` 再由證據腳本讀回,現在產生器直接呼叫重算)。
- 驅動腳本存檔:當時在 DOSBox-X 上產生原始紀錄的腳本,檔頭標了「存檔」,路徑保留當時的工作環境,不保證能直接執行;
  只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)使用。
  - 續六十五~七十七:`t_v*.py`、`*_setup.py`、`mk_t_v*.py`、`reach_battle.py`、`inj_s77.py`、`v21_*.sh` 等;
    證據 JSON 的 `drivers` 欄位指向這裡。
  - 續四十六~六十四(依各檔標頭說明與輸出路徑歸類,未逐一重跑):
    通用斷點記錄 `bp_log.sh`、`bp_loop.sh`、`dlg_step.sh`;
    單次攻擊 / 施法受控測試 `exp_test.sh`、`lvl_test.sh`、`terr_test.sh`、`spell_cast.sh`;
    `dump_collect.sh`(collect_targets_in_range)、`sel_setup.sh`、`sel_dump.sh`(`ev_s65` 的 selector);
    `mix_setup.sh`(ai_action_choice)、`it_setup.sh`(ai_item_score)、`mv_setup.sh`(ai_move_nearest)、
    `sc_setup.sh`(ai_spell_score)、`rg_setup.sh`、`rg_setup2.sh`(rest_recover)、`kc_setup.sh`(real_kill_corpse)、
    `s9_setup.sh`(spell9_path);`pa_setup.sh`、`pa_setup2.sh`、`pa_log.sh`(ai_physical_candidate);
    `tr_setup.sh`、`tr_setup2.sh`、`tr_setup3.sh`、`tr_log.sh`(ai_physical_untested_branches);
    `sl_setup.sh`、`sl_tie_setup.sh`、`sl_log.sh`(move_landing_select);
    終端輸出裡的記錄腳本 `sc_log.sh`(ai_spell_score)、`hl_setup.sh`(ai_heal_score)、`it_log.sh`(ai_item_score)、
    `mix_log.sh`(ai_action_choice)、`rg_log.sh`(rest_recover)、`s9_log.sh`(spell9_path)、
    `run_case.sh`、`lvl_print.py`(level_up)、`units_print.py`(傾印欄位列印)。
