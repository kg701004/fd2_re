# 證據產生器(續六十五~七十七)

`docs/knowledge-base/evidence/` 裡下列 14 份證據 JSON 都是由本目錄的產生器從原始紀錄重算出來的,
不是手寫的。產生器逐項 `assert` 判準與預測,任何一項不符就失敗。

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

## 執行

```
python run_all.py              # 全部重算到暫存目錄,與已提交檔案逐 byte 比對;全部 IDENTICAL 才 exit 0
python run_all.py ev_s76       # 只跑一個
python run_all.py --selftest   # 比對器與輸入檢查的正反對照
python mut_s76.py              # 變異測試:先跑未變異對照,再逐一跑每個變異(都要以 AssertionError 失敗)
```

`run_all.py` 與變異測試都不會覆寫已提交的證據檔。要更新證據時才直接執行產生器(`python ev_s76.py`),
它會寫到 `docs/knowledge-base/evidence/`。

## 輸入不在 git 裡

產生器讀的原始紀錄(`.wsl_build/` 的 DOSBox-X 傾印、追蹤、截圖與記錄檔,共約 27 MB)、
`extracted/` 與原版遊戲檔(`org_game/`,可用 `FD2_GAME_DIR` 指到別處)都被 `.gitignore` 排除:
原版程式與資產受著作權保護(見倉庫 `README.md`),記憶體傾印裡有原版程式與資料。

所以每個產生器啟動時先呼叫 `_evpaths.require_inputs()`,依 `inputs_manifest.json` 比對每一筆輸入的
大小與 sha256;缺檔或內容不同時以 exit code 3 結束並列出每一筆(`run_all.py` 顯示為 `MISSING_INPUT`)。
在沒有這些原始紀錄的機器上,結果是 `MISSING_INPUT`,不是一份算錯的證據。

`inputs_manifest.json` 由 `build_manifest.py` 產生(以 `_trace/sitecustomize.py` 的 audit hook 記錄實際開啟的檔案);
只有原始紀錄確實換過時才重建。

## 限制

- `ev_s71`、`ev_s72`、`ev_s73` 的輸出含 `str(Path)`(Windows 路徑分隔字元),逐 byte 相同只在 Windows 上成立。
- `IDENTICAL` 證明可重現,不證明正確;正確性由產生器裡的 `assert` 與變異測試負責。

## 其他腳本

- 輔助模組(產生器會匯入或執行):`an_f.py`、`an_ev.py`、`live.py`、`rng.py`、`sim_path.py`、`sim_dialog.py`、
  `dato_match.py`、`walk_after.py`。
- 驅動腳本存檔(`t_v*.py`、`*_setup.py`、`mk_t_v*.py`、`reach_battle.py`、`inj_s77.py`、`*.sh` 等):當時在
  DOSBox-X 上產生原始紀錄的腳本,證據 JSON 的 `drivers` 欄位指向這裡。檔頭標了「存檔」,路徑保留當時的
  工作環境,不保證能直接執行;只對原版 FD2.EXE(md5 33464c81e6a364fd0660141139aa8e6e)使用。
