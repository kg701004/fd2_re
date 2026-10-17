# SESSION-HANDOFF 2026-10-07

> 依 `AI_Development_Standard/00_Global/Project_Continuity.md` 撰寫:明確區分完成/未完成/
> 需人決定,每一項標註**驗證等級**,不把未驗證的寫成已驗證(本線依據是 FD2.EXE 反組譯;原版 DOSBox-X 實機軌跡只用於死函式反驗與擷取規劃)。
> 前一份:[`SESSION-HANDOFF-2026-09-19.md`](SESSION-HANDOFF-2026-09-19.md)。

## 0. 範圍與主軸

**本文件只交接「函式清單求完整」這一條線**:commit `8adabab6` ~ `687ecb6b` 中與 `tools/function_inventory.py` /
`docs/data/function_names.json` 相關的 11 個 commit,全部已推送至 `fork remaster-local`。
歸檔後又有 `b9c62ec0`、`15bb1aff`、`88c4cf74` 三個 commit(續九十六 ~ 九十八:原版實機軌跡反驗死函式、執行位址收進倉庫、下一輪擷取規劃),同樣已推送。
同期另有 DOSBox-X 動態驗證(續六十五 ~ 七十七)與證據產生器收進倉庫等 commit,**不在本文件總結範圍**,見 `git log 0c2e139f..687ecb6b`。

目標(使用者 2026-10-06 定):FD2.EXE 的每個函式入口都要讀過並命名,而且**先把分母做對**。
逐步紀錄在 [`98-tooling-infrastructure.md`](98-tooling-infrastructure.md) 的續七十八 ~ 續九十八。

---

## 1. 驗證等級對照

| 等級 | 意義 | 本線用量 |
|---|---|---|
| **靜態 RE** | FD2.EXE 反組譯確定,未經實機 | `function_names.json` 全部 1149 筆(`confidence: static_re`) |
| **位元組證據** | 每筆名稱的 `{at, insn}` 或跳表 `{fixup_from, table, index}` 逐字比對 FD2.EXE 反組譯通過 | 1149 / 1149(`--check-names`) |
| **工具自驗** | `--selftest` 通過,新程式碼做定點突變且以 FAIL(非 Traceback)抓到 | `function_inventory.py`:續九十一 7 / 7、續九十五資料突變 1 / 1;`plan_trace_coverage.py`:續九十八 17 / 17、續一百零三 8 / 8 |
| **產物重生** | 重跑產生器(讀 FD2.EXE 反組譯)與已提交檔逐位元組比對 | `verify_generated_artifacts` 23 / 23(續九十七加入 `live_exec_addresses.json`、續一百加入 `live_scene_entries.json`) |
| **原版實機** | DOSBox-X 跑原版 EXE | 「死函式不會執行」反驗:13 份不重複軌跡、626 / 1356 個入口有執行紀錄(續九十六 ~ 九十七、續一百、續一百零二、續一百零四 ~ 零六);名稱以場景分段軌跡**抽驗** 22 條規則 22 / 22 成立(續一百),**其餘名稱未經實機** |

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
| 名稱的實機驗證 | 部分 | 名稱本身全部是靜態 RE,沒有逐一下斷點;「死函式不會執行」已用 **13 份不重複**的原版 DOSBox-X 實機軌跡反驗(續九十六的「234 份」是同一份的複本,續九十七訂正;續一百加一輪從開機錄到底的;續一百零二加一個敵方回合;續一百零四加法術 9..27 與 `[0x53af9]=1` 的敵方回合 5 份;續一百零五加 AIL 除錯環境的開機軌跡;續一百零六加 `fpu=false` 的 387 模擬器軌跡;續一百零七起另有逐函式的參數 / 回傳紀錄,見下一列):52 個 weak 入口的本體指令沒有一條執行過,0x46915 只有 span 尾端與活路徑共用的樁表有紀錄。執行位址收在 `docs/data/live_exec_addresses.json`,這項反驗已進 `function_inventory.py --selftest`(續九十七)。續一百另以場景分段軌跡抽驗名稱 22 / 22,並抓到 `0x28f65` 摘要錯誤(是隊員間轉交,不是寄放;名稱沿用、摘要已改) |
| 名稱的逐函式實機反驗 | 4 份紀錄、534 個入口通過;摘要已改正 3 + 16 筆 | 續一百零七:修補的 dosbox-x 一次記下所有入口的參數與回傳(`FD2_HARNESS_CALLLOG`),`tools/verify_names_by_calllog.py` 驗紀錄可信、呼叫圖、間接 call 目標與可機械檢查的宣稱。續一百零八:城鎮 / 商店 / 教會 / 戰鬥指令 / 法術 / 敵方 AI / 存讀檔再錄 3 輪,執行入口 387 → 534;規格檔 `docs/data/function_specs.json`(47 個函式 59 條,有紀錄 50 條全部成立)與逐函式事實檔 `docs/data/function_call_profiles.json`;反驗出 3 筆摘要錯誤(`draw_unit_panel_by_side` 參數順序、`action_ring_select` 回傳值、`open_dialog_box` 的 load_res 參數順序),已改正。續一百零九:`tools/screen_summaries_by_calllog.py` 把有紀錄的 451 筆摘要全掃(參數個數 vs 呼叫端清堆疊、參數名型別 vs 實際值、字串參數、列舉完的回傳值),18 個候選逐筆看反組譯:改正 14 個函式 + 篩選抓不到的 2 個(`blit_res_cell_sprite` 參數順序、`draw_number` 補參數列),1 個非錯誤;結論在 `docs/data/summary_screen_review.json`,規格擴充到 57 個函式 71 條。篩選看不到型別相容的對調(指標對指標),也不檢查沒有型別意涵的參數名。待做:其他法術 handler、出擊選人;型別篩選看不到的部分仍要以 `--json` 剖面人工核對。續一百一十:inventory argc 改為沿控制流(`derive_native_argcounts.callee_argc`),61 筆改變,與呼叫端清堆疊一致 480 → 518、多算 6 → 0;事實檔已重產。續一百一十一:篩選補 `param_region`(來源參數指到 VGA)與靜態 `param_role`(目的只讀不寫 / 來源被寫入,不需要實機紀錄),改正 `apply_status_spell_to_targets` 參數順序;實機補錄 cl5(法術 / 道具 / 地圖演出)與 cl6(教會復活 / 出擊選人),執行入口 534 → 586,再改正 5 筆摘要(含 `draw_unit_hp_bar` 參數順序),規格 58 個函式 74 條、有紀錄 67 條全部成立。續一百一十二:殘留風險逐項查證 —— 靜態個數篩選(沒有紀錄的函式)、角色篩選追到轉交(可比 59 -> 97),改正 6 筆摘要;續一百一十一「道具表沒有 type 0xb」是錯的(道具 206 / 207);cl7 錄到地圖縮圖(F1)、MP 回復道具、升級學法術,執行入口 586 -> 591,規格 60 個函式 79 條、有紀錄 75 條全部成立。續一百一十三:控制流引擎 + 呼叫端值流型別篩選(`param_flow`,以實機紀錄校準零矛盾、零誤報),零存取 11 -> 0,角色可比 97 -> 108;改正 `blit_res_cell_xy`、`wav_parse_chunks` 參數對調。續一百一十四:突變存活 22 -> 0(65 個全 KILLED;引擎加迭代上限、刪 2 個多餘條件、補 15 題),param_flow 判不出的 34 個分類後直接讀反組譯,改正 `anim_draw_and_advance`、`unit_present_intro_frames`、`sortie_required_member_check` 參數列與 `blit_anim_frame` 內文;實機補錄 cl9 / cl11 / cl12(紀錄 10 份、執行入口 591 -> 616、規格有紀錄 77 條全部成立,未執行剩 2 條只能靜態確認);`_cstr` 改成換行算字串的一部分。續一百一十五:`_cstr` 加門檻(含換行的內容可列印字元 >= 3 才算字串)、規格加 unreachable 標記(未執行 2 條都已交代,標了卻被執行就 FAIL)、以 `...` 省略與佔位名的摘要全部讀完(改正 `pan_view_left_to_panel` 參數列,佔位名 18 -> 0)。續一百一十六:篩選工具補三個缺口(沒判的不再算已比、省略的摘要進靜態篩選、參數名登錄未分類 = 錯誤)並加 `param_unread`;新增 `tools/param_dossier.py`(資料卡 + 人工閱讀登錄 + 涵蓋數字);改正 8 筆參數列。具名參數 861:機器比過 720、只有人工讀過 36、都沒有 105。續一百一十七:新篩選 `param_name`(呼叫者的參數原樣傳給被呼叫者時兩邊名稱要相容;597 條邊、397 個參數)、值規則 nibble / seg16 / dosmem,無型別名稱 65 -> 36;改正 6 筆參數列。具名參數 864:機器比過 745、只有人工讀過 28、都沒有 91。續一百一十八:以 `...` 省略的 23 筆摘要全部補齊、沒有依據的 92 個參數逐個讀完(登錄 95 -> 181 筆)、無型別名稱 36 -> 18;改正 `io_set_mode` 參數列與 `ail_ini_parse_line`、`action_ring_select` 內文。實機補錄 cl13 / cl14(紀錄 12 份、執行入口 616 -> 621;武器店買賣與 AIL 除錯啟動,補滿 3 個紀錄太少的參數)。具名參數 899:機器比過 799、只有人工讀過 95、都沒有 5。另量到 255 個函式、709 個堆疊格沒有參數名(不在這個分母裡)。續一百一十九:那 255 個函式全部補上參數列(6 個其實沒有參數,寫成 `()`),讀出 18 處寫錯的摘要;無型別名稱再改 3 個;原訂補錄的 2 個參數改由唯一的呼叫點靜態定案。具名參數 1525:機器比過 1176、只有人工讀過 349、都沒有 0(登錄 436 筆) |
| 下一輪擷取 | 建議 | 敵方 AI 施法 / 攻擊 / 道具已錄(續一百零二,實際 +30;規劃工具的 +158 把指令 handler 表後面的子孫全算進去,是上界);法術 handler 表(續一百零四,+42)與 `ail_startup` 的除錯分支(續一百零五,`FD2_HARNESS_DOS_SET` 設 `AIL_DEBUG`,實際 +21、估 +133)已錄;387 模擬器的安裝 / 卸除(續一百零六,`FD2_HARNESS_FPU=false`,實際 +8、估 +72)已錄;重跑後排前面的是 `emu_ea_sib`(模擬器指令 handler,要在 `fpu=false` 下跑到會執行浮點指令的場景;續一百零六整輪只模擬了 7 條)、浮點 printf、`__math87_err`(錯誤路徑)、`map_attack_sequence`;防拷密碼畫面本版不可達(`0x118aa` 是無條件跳過),續一百零三起 `plan_trace_coverage.py` 以靜態可達分析排除,不再列為前線 |
| doc98 續八十稱 0x4a424 為「浮點模擬器主體」 | 已在續九十一訂正 | 它是 SIB 解碼 `emu_ea_sib`;舊句保留為歷史,訂正寫在續九十一 |
| 部分摘要只列被呼叫者 | 刻意保留 | 參數名或內部步驟沒讀到的,寫「N 個參數」或只列被呼叫者,不寫推測(續九十四列了撤掉的推測) |

---

## 4. 需要人決定

- 名稱的 DOSBox-X 實機抽驗已做一輪(續一百,22 / 22);擴大到逐函式已決定(2026-10-08),以呼叫紀錄工具進行(續一百零七)。

---

## 5. 入口與工具

| 我想… | 用 |
|---|---|
| 看某個位址是哪個函式、名稱、證據、本體反組譯 | `python tools/function_inventory.py --card 0x位址` |
| 看覆蓋率 | `python tools/function_inventory.py --coverage` |
| 決定下一輪原版實機擷取跑哪個場景 | `python tools/plan_trace_coverage.py`(續九十八:戰場指令環 +369、城鎮教會 / 商店 / 出擊選人、從開機就錄 +231 —— 這幾項續一百已擷取;敵方 AI 施法續一百零二、法術 handler 續一百零四、AIL 除錯續一百零五已擷取;收益是上界;靜態走不到的呼叫點不算前線) |
| 有新的原版軌跡時更新實機執行位址 | 新軌跡放進 `.wsl_build/` 後 `python tools/verify_dead_functions_vs_traces.py --export docs/data/live_exec_addresses.json .wsl_build`(需要 capstone;內容驗不過的軌跡自動略過;已登錄 `verify_generated_artifacts`),再調高 `function_inventory.py` 的 `LIVE_ENTRY_FLOOR` |
| 從開機就錄的擷取、依場景看第一次執行的函式與名稱抽驗 | `FD2_HARNESS_BREAK_START=1` 啟動 `dosbox_harness.sh`(要 DOS 環境變數時加 `FD2_HARNESS_DOS_SET="NAME=VALUE …"`,續一百零五);分段檔放 `.wsl_build/live_s100_segments/` 後 `python tools/trace_scene_names.py --export docs/data/live_scene_entries.json .wsl_build/live_s100_segments`,再 `python tools/trace_scene_names.py`(續一百) |
| 逐函式實機反驗(參數 / 回傳 / 呼叫端) | 修補版 dosbox-x 見 `tools/dosbox/fd2_calllog_patch.py` 的建置步驟;`python tools/verify_names_by_calllog.py --write-entries <入口檔>`,以 `FD2_HARNESS_DOSBOX_BIN=… FD2_HARNESS_CALLLOG=<入口檔>` 啟動 harness,結束後把 `CALLLOG.TXT` 複製成 `.wsl_build/<名稱>_CALLLOG.TXT`,跑 `python tools/verify_names_by_calllog.py --logs-dir .wsl_build [--json 審閱剖面]`;重產事實檔 `--export docs/data/function_call_profiles.json --logs-dir .wsl_build`(續一百零七 / 一百零八) 續一百二十二:要逐幀看畫面效果時,在貼圖之後下斷點、傾印線性 0xa0000 起 64000 bytes 與 `[0x53a65]` 的調色盤離線重建,再用視窗截圖反過來核對(做法與要避開的地方見 doc98 續一百二十二、doc35 §18)。 續一百二十三:在函式收尾下斷點之前,先查那個位址有沒有別的函式跳進來(`0x15309` 是共用結尾);`BPDEL` 只收序號或 `*`;停在斷點時的視窗截圖是上一步的畫面(doc98 續一百二十三)。 續一百二十四:obj3 的資料(法術列、道具列、亂數)執行期位移是 0x192000,不是 0x19c000;改單位 HP 做實驗要在結束回合的休息之後改(休息會補 MaxHP / 5);只在某個動作裡才要的斷點,等那個動作的入口停下才設(doc98 續一百二十四)。續一百二十五:遊戲執行中不能傾印記憶體(要停在除錯器裡),執行中只截圖;錄製腳本每一站都先寫檔;剛進戰場時開場對白還在跑,單位還沒全部出現,設定要等對白結束(doc98 續一百二十五)。續一百二十六:計時讀線性 0x46c 的 BIOS tick,停在除錯器時不走(模擬時間,cycles 5000);要讓戰鬥直接結束,在結束我方階段時的 0x1d8aa 寫 [0x53ecc];法術要範圍內有目標才施放得了(doc98 續一百二十六)。續一百二十七:正式進某章戰場要用 fd2_chapter_sweep 的 prepare_chapter_save 完整隊伍存檔(只改章節位元組會卡在出戰選擇);harness 的 cycles 用 WSL 包裝腳本換,不改工具;按鍵仍要隔 6 秒以上(doc98 續一百二十七)。續一百二十八:跳表的分段看 `verify_event_dispatch_table.py` 輸出的 `dispatch` 欄(由程式碼裡的 `call [reg*4 + 基底]` 導出,不是看格子是不是函式入口);用 heredoc 寫含位元組字面值的修補會壞掉(doc98 續一百二十八)。續一百二十九:換 cycles 的包裝腳本要含 `FD2_CALLLOG_ENTRIES` 字串(harness 用 grep 檢查 binary);cycles 2500 下按鍵會被漏讀,改對同一視窗 keydown、0.3 秒後 keyup(doc98 續一百二十九)。續一百三十:要在不停住遊戲的情況下逐次讀某個變數,把讀它的那條指令的執行期位址放進呼叫紀錄的入口檔(`FD2_HARNESS_CALLLOG_CAP` 調大、`FD2_HARNESS_CALLLOG_DUMP=0`),E 紀錄帶暫存器,不必擷取畫面;新證據附產生器(`evidence/generators/`,加進 `build_manifest.py`)(doc98 續一百三十)。續一百三十一:要看某一幀的地圖格,停在 `draw_terrain_layer` 入口 0x11eee(緩衝裡是上一幀,EAX = 緩衝 + 0x8088)傾印地圖緩衝離線比較,不必截圖;harness 的 `key --wait 1` 按住會觸發重複,選單操作用 `fd2_chapter_sweep.send_keys`(doc98 續一百三十一)。續一百三十二:呼叫紀錄的 EIP 是補零 8 位(`001b12a0`),grep 要寫全;續一百三十一的「第二輪沒錄到」就是少了補零(doc98 續一百三十二)。續一百三十三:在全部 sprite 裡找「唯一相符」之前,先排除全透明的 sprite(FDICON 有 225 個,合成後只剩上層的圖一定全中);比對圖示前先讀完函式在圖示之後還畫了什麼(HUD 圖示下 8 列蓋著 HP 數字)(doc98 續一百三十三)。 |
| 篩出摘要與實機紀錄矛盾的函式 | `python tools/screen_summaries_by_calllog.py [--json 候選明細]`:讀已提交的事實檔、摘要與 EXE;rc 1 = 有未核對的候選或 review 檔錯誤。看過反組譯後在 `docs/data/summary_screen_review.json` 記 `fixed` / `not_error`。改摘要或重產事實檔後都要重跑(續一百零九)。續一百一十一起含靜態的 `param_role`,沒有實機紀錄的函式也會篩;續一百一十二起沒有紀錄的函式以靜態清堆疊比個數,角色篩選追到轉交給被呼叫端的參數;續一百一十三起沿控制流,另有靜態 `param_flow`(呼叫端推的值判型別);續一百一十六起 `...` 之前的名稱照常比、另有 `param_unread`,參數名必須在名單或 `OPAQUE_NAMES` 裡(否則 rc 1);續一百一十七起另有靜態 `param_name`:候選鍵 `p<k>:<呼叫者的參數名>`,兩個名稱其實同義就加進 `NAME_SAME`、是特稱與泛稱就加進 `NAME_ISA`(兩張表不能跨型別),否則改摘要或記 `not_error`;續一百一十八起摘要已沒有 `...` / `..`,新增名稱時記得放進型別名單;續一百一十九起被呼叫端是 C runtime(`LIBC_FUNCS`)的邊只比型別與讀寫角色(`libc_agree`),新補參數列的 C runtime 函式要加進那份名單 續一百二十:`param_unread` 會跟著跳出本體的 jmp / 條件跳躍走(`tail_params_read`,上限 256 條指令),推完常數就尾跳到別的 handler 收尾段的函式不再報成「沒有人讀」(13 筆 not_error 改由工具自己判定,分母「param_unread 跳出本體後才引用」);候選 55 -> 42。 續一百二十一:改參數名會連帶改掉 `param_name` 候選鍵裡的名稱(`p<k>:<名>`),review 的那一列與 selftest 的釘值要一起改,否則舊列報過期、新候選報未核對;op 名稱(`DOC_OP_NAMES`)改名後要重生 `native_argcounts.json` 與 `chapter_beats/`。 |
| 讀一個函式的參數 / 查還有哪些參數沒有依據 | `python tools/param_dossier.py NAME [--dis N]`:每個堆疊格的引用指令、原樣轉交、實機值、呼叫端來源。讀完在 `docs/data/param_read_review.json` 登錄(依據指令必須真的引用該參數);`--coverage` 印機器比過 / 只有人工讀過 / 都沒有,`--worklist` 列出最後一類(續一百一十六);續一百一十七起另印「名稱沿呼叫邊比過」的個數,它不計入機器比過;續一百一十八起登錄多一種依據 `reg`(暫存器傳參的函式:`at` 是本體第一個提到該暫存器、而且不是單純覆寫它的指令);續一百一十九起再多三種:`via`(暫存器原樣交給被呼叫端)、`raw`(走不出本體的函式,只看入口的直線段)、`indirect`(只經函式指標被呼叫而本體不讀的參數:fixup + 間接 call + 那一格的 push),`reg` 不再把 `push r` 當成讀 |
| 驗每一筆名稱的位元組證據 | `python tools/function_inventory.py --check-names` |
| 重生清單 / 結構性命名 | `python tools/function_inventory.py docs/data/function_inventory.json`、`--structural docs/data/function_structural_names.json` |
| 自我測試 | `python tools/function_inventory.py --selftest`(約 35 秒;續九十九起真實 EXE 段的 build 只算 3 次) |

改 `function_names.json` 後要重生 `function_structural_names.json`,否則 selftest 的「已提交的結構性命名產物與現算相同」會失敗。
跳表名稱(`event_handler_N`、`command_handler_N`)必須附 `{fixup_from, table, index}` 證據,否則 `--check-names` 失敗。
