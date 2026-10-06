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
python sweep_literals.py [ev_s65b ...]   # 每個數字常數 +1 重算:找出寫進證據卻沒有判準擋得住的手寫值
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
  切出當時印下的值相同。

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

## 限制

- `IDENTICAL` 證明可重現,不證明正確;正確性由產生器裡的 `assert` 與變異測試負責。
- 原始紀錄只有倉庫外同一顆硬碟上的本機備份(`fd2_re_evidence_raw_backup/`,最新一份 `evidence_inputs_all_20261006.tar.xz`
  含清單上全部 1759 個非遊戲檔,遊戲檔在 `*_20261005b`),沒有第二份;硬碟損壞時產生器全部變成 `MISSING_INPUT`。
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
  `_terrain.py`(地形修正規則,`ev_terrain_modifier` 與 `ev_attack_path_selection` 共用)。
- `tx_console.py`:終端輸出與對話紀錄的匯出、比對、抽出(見「終端輸出與摘錄」);取代當時在 scratchpad 的
  `tx_index.py` / `tx_export.py`。
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
