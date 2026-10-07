# SESSION-HANDOFF 2026-10-07

> 依 `AI_Development_Standard/00_Global/Project_Continuity.md` 撰寫:明確區分完成/未完成/
> 需人決定,每一項標註**驗證等級**,不把未驗證的寫成已驗證(本線依據一律是 FD2.EXE 反組譯)。
> 前一份:[`SESSION-HANDOFF-2026-09-19.md`](SESSION-HANDOFF-2026-09-19.md)。

## 0. 範圍與主軸

**本文件只交接「函式清單求完整」這一條線**:commit `8adabab6` ~ `687ecb6b` 中與 `tools/function_inventory.py` /
`docs/data/function_names.json` 相關的 11 個 commit,全部已推送至 `fork remaster-local`。
同期另有 DOSBox-X 動態驗證(續六十五 ~ 七十七)與證據產生器收進倉庫等 commit,**不在本文件總結範圍**,見 `git log 0c2e139f..687ecb6b`。

目標(使用者 2026-10-06 定):FD2.EXE 的每個函式入口都要讀過並命名,而且**先把分母做對**。
逐步紀錄在 [`98-tooling-infrastructure.md`](98-tooling-infrastructure.md) 的續七十八 ~ 續九十四。

---

## 1. 驗證等級對照

| 等級 | 意義 | 本線用量 |
|---|---|---|
| **靜態 RE** | FD2.EXE 反組譯確定,未經實機 | `function_names.json` 全部 1149 筆(`confidence: static_re`) |
| **位元組證據** | 每筆名稱的 `{at, insn}` 或跳表 `{fixup_from, table, index}` 逐字比對 FD2.EXE 反組譯通過 | 1149 / 1149(`--check-names`) |
| **工具自驗** | `--selftest` 通過,新程式碼做定點突變且以 FAIL(非 Traceback)抓到 | `function_inventory.py`:續九十一 7 / 7、續九十五資料突變 1 / 1 |
| **產物重生** | 重跑產生器(讀 FD2.EXE 反組譯)與已提交檔逐位元組比對 | `verify_generated_artifacts` 21 / 21 |
| **原版實機** | DOSBox-X 跑原版 EXE | 本線**未使用** |

**本線沒有任何結論依賴 remake。**

---

## 2. 已完成(可量測)

| 指標 | 2026-09-19 交接時 | 現在 |
|---|---|---|
| 函式入口(分母) | 1102 | **1356**(剔除假入口 7、加函式指標入口、LE 進入點 1、死函式島 44,剔除 AIL_startup 假入口與資料裡的 E8 命中各 1) |
| strong 入口 | 858 | **1304**(219 個 weak 經 FD2.EXE 反組譯確認「唯一呼叫端是可達 call」而升級,含跳表 case 後面的 11 個) |
| weak 入口 | — | **52** = 44 個死函式島 + 8 個唯一呼叫端在死函式裡 |
| 名稱登錄表 | 80 筆 | **1149 筆** |
| 有名稱的入口 | — | **1356 / 1356**(`--coverage`:文件記載為入口 0、無名 0) |
| 名稱摘要裡的「推定 / 未逐條讀 / 未核對」 | — | **0**(續九十二 ~ 九十三逐筆讀 FD2.EXE 反組譯解除;`isatty` 那筆只是說明舊推定已確認) |
| Watcom 函式庫比對找回的原始符號 | — | 82 個 |
| 結構性自動命名(含登錄表) | 258 筆 | **0 筆**(沒有 strong 入口需要自動命名) |

回歸看守:`--selftest` 的真實 EXE 段檢查「全部入口都有名稱」並有反向控制(續九十五)。

---

## 3. 未完成 / 已知限制

| 項目 | 狀態 | 說明 |
|---|---|---|
| 52 個 weak 入口 | 靜態 RE 已到頂 | 唯一呼叫端都在沒有執行路徑的死函式裡,「呼叫端可達」這個方法本來就證明不了;身分已寫在登錄表 |
| 名稱的實機驗證 | 部分 | 名稱本身全部是靜態 RE,沒有逐一下斷點;但「死函式不會執行」已用 **4 份不重複**的原版 DOSBox-X 實機軌跡反驗(續九十六的「234 份」是同一份的複本,續九十七訂正):52 個 weak 入口的本體指令沒有一條執行過,0x46915 只有 span 尾端與活路徑共用的樁表有紀錄。執行位址收在 `docs/data/live_exec_addresses.json`,這項反驗已進 `function_inventory.py --selftest`(續九十七) |
| doc98 續八十稱 0x4a424 為「浮點模擬器主體」 | 已在續九十一訂正 | 它是 SIB 解碼 `emu_ea_sib`;舊句保留為歷史,訂正寫在續九十一 |
| 部分摘要只列被呼叫者 | 刻意保留 | 參數名或內部步驟沒讀到的,寫「N 個參數」或只列被呼叫者,不寫推測(續九十四列了撤掉的推測) |

---

## 4. 需要人決定

- 是否要對名稱做 DOSBox-X 實機抽驗(授權已在記憶裡,但量大,本線沒有把它列為建議)。

---

## 5. 入口與工具

| 我想… | 用 |
|---|---|
| 看某個位址是哪個函式、名稱、證據、本體反組譯 | `python tools/function_inventory.py --card 0x位址` |
| 看覆蓋率 | `python tools/function_inventory.py --coverage` |
| 有新的原版軌跡時更新實機執行位址 | 新軌跡放進 `.wsl_build/` 後 `python tools/verify_dead_functions_vs_traces.py --export docs/data/live_exec_addresses.json .wsl_build`(需要 capstone;內容驗不過的軌跡自動略過;已登錄 `verify_generated_artifacts`),再調高 `function_inventory.py` 的 `LIVE_ENTRY_FLOOR` |
| 驗每一筆名稱的位元組證據 | `python tools/function_inventory.py --check-names` |
| 重生清單 / 結構性命名 | `python tools/function_inventory.py docs/data/function_inventory.json`、`--structural docs/data/function_structural_names.json` |
| 自我測試 | `python tools/function_inventory.py --selftest`(約 2.5 分鐘) |

改 `function_names.json` 後要重生 `function_structural_names.json`,否則 selftest 的「已提交的結構性命名產物與現算相同」會失敗。
跳表名稱(`event_handler_N`、`command_handler_N`)必須附 `{fixup_from, table, index}` 證據,否則 `--check-names` 失敗。
