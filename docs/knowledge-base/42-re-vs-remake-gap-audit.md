# 42 — RE 已記錄 vs remake 已實作:落差稽核

> **2026-09-02:`remake/` 已整個移除(使用者明確指示)。** 本檔逐項核對「remake 程式碼
> 實際做了什麼」的方法論本身(讀 code、跑 remake 截圖佐證)已失去對象——`remake/internal/
> battle`、`remake/cmd/fd2` 等路徑已不存在。本檔內容為移除前的歷史紀錄,不代表現況。
> 詳見 `91-worklist.md` M5 段落、memory `feedback_fd2_re_remake_verification_paused`。

> 目的:逐一核對「RE knowledge-base 已記錄的機制」與「remake 程式碼實際做了什麼」,列出落差與優先度。
> 方法:每項機制先讀對應 doc,再 grep/讀 `remake/internal/battle`、`remake/cmd/fd2` 的實作,以 code 為準,不憑印象判定。
> 2026-07-25 重新校正本表：撤回已被後續 code 推翻的「零命中／完全沒有」斷言。序章主角隊進場(staging)由另一 agent 處理,本篇不重複列。
> 狀態符號:✅已實作(含公式/資料對齊) 🟡部分(做了一半或簡化) ❌缺(RE 有記錄,remake 未做)。

## 2026-07-27 進度停滯審計

近期 commit 主要增加 E0 raw adapters 與斷言撤回，沒有等比例增加可操作的
campaign/UI 路徑。根因不是反組譯工具不足，而是 E0→runtime→E2 的串接缺口：
`main.go` 仍是 monolithic scene/input/draw owner；UI contract 缺 deterministic
input/state trace 與 screenshot gate；30 章 postbattle graph 尚未逐章驗收；worklist
勾選數也容易把函式級成果誤讀成玩法完成。

本表後續採用「垂直閉環」判定：raw slice 若沒有 caller/data contract、runtime
consumer、regression，且 UI 項目沒有 E2 artifact，只能列為 🟡，不得提升為完成。
下一個優先工作不是再開新的孤立 offset，而是把 title→dialog→battle→postbattle
hub→preparation/town 做成可重播 input trace；item effect、AI runtime 等新 RE
只有在能直接供應該垂直鏈時才解除 fail-closed。

> **2026-07-26 native-command correction**：本表中 legacy `magic.go`／`CastArea` 的舊逐招
> 勾選，不能再當作原版 command runtime 的完成宣告。權威逐 ID dataflow 與 strict engine 邊界是
> SDD `56 §UI-03`，UI 證據則是 `57 §UI-03`；未有 E0 target、transaction、renderer 證據的 ID
> 必須維持 fail-closed。下列舊表列已改為只描述 normalized approximation，不再宣稱與原版同義。

## 總表

| 機制 | RE doc 出處 | remake 狀態 | 證據 | 優先度 |
|---|---|---|---|---|
| 物理攻擊:基礎傷害 AP−DP | doc02 §4.1 | ✅ | `combat.go:12` `dmg := a.EffectiveAP() - d.EffectiveDP()` | — |
| 物理攻擊:**地形 AP/DP% 修正** | native `0x1acf3`、`0x51a12/0x51a2a`、doc11 | ✅原版逐格資料 | `map.json` 已有 raw `tiles`+`native_terrain_control`; `battle.Load` 只在完整驗證後導出逐格 FDSHAP control byte+1，`TerrainAPDPPct` 直接採 static table：0→(+5,0)、1/5→(0,0)、2/3→(-5,+10)、4→(-5,-5)。舊／不完整 map 才保留 Cost fallback，相容性而非原版語意。 | 低 |
| 物理攻擊:**暴擊(DP÷2)** | doc02 §4.1「暴擊時 DP=守方DP/2」 | ✅ | `combat.go AttackWithRNG`:`CritPct>0 && rng.Intn(100)<a.CritPct` 觸發後 `dp/=2`,順序照 notes.md(先減半再套地形%);`CritPct` 來源 `resist_crit.json`(EXE 0x5219B,已與 doc02 §7.2 逐職業交叉驗證吻合) | — |
| 物理攻擊:**命中率 (HIT−EV)%** | doc02 §4.1 | ✅(2026-08-14 補完) | `model.go EffectiveHIT/EffectiveEV` + `combat.go rollsHitPct`;HIT/EV 基礎值原本是固定近似值(export_units.py DEFAULT_HIT=90/DEFAULT_EV=5),現已用兩份反組譯證據算出真值:(1) native sub_1B750(0x1B750..0x1B83D,IDA Pro 9.4 + Capstone 雙工具反組譯,`docs/data/fd2_runtime_equipment_recalc_1b750_ida.txt`)證實 HIT/EV 起始值共用同一個 raw signed word `+0x3e`(=doc32 已命名的 persistent base DX),再各自加上已裝備物品的 item.json hit/ev word;(2) 建構器 0x10c50(official IDA 9.4 pseudocode,`56` SDD「2026-07-27 — constructor inventory flag materialization」)證實出場 inventory 只有前兩個 raw slot 會被自動判定為「已裝備」。`export_units.py` 的 `spawn_equipped_item_ids()`/`hit_ev_for_unit()` 已實作此公式,33 張地圖的 `map*_units.json` 已用 `tools/patch_units_hit_ev.py`(只改 hit/ev 兩個欄位,不動其餘既有欄位如 native_treasure_event_rules)重新算過,`go test ./...` 全綠 | — |
| 物理攻擊:**傷害隨機化(0.9×max~max−1)** | doc02 §4.1 | ✅ | `combat.go AttackWithRNG` 呼叫 `magic.go randomizeAmount`(與法術共用同一公式) | — |
| native IDs24/28/29/31 derived strike | SDD56 UI-03 | 🟡 strict state-only | `ExecuteNativeCommand24`／`ExecuteNativeCommandDerivedStrike` 已依 `0x276EC` 的 verified multiplier 寫 final HP delta；two-stage UI、multi-hit/SFX 未接。legacy `CastArea` 不是證據 | 高 |
| normalized spell attack/heal/hit | doc02；legacy `magic.go` | 🟡 approximation(legacy path) | `CastArea` 有可玩結算，但 native command ID、target geometry、effect family 和 renderer 沒有逐項閉合；不得以其數字證明原版法術完成。**注意**:這行只描述 legacy `CastArea` 路徑——2026-08-14 已用 `FD2_SHOT_COMMAND_FORCE`/`FD2_SHOT_COMMAND_CONFIRM` 對native command 0(火炎術)跑過選單開啟→選目標→游標確認→傷害結算全流程,remake 端結果是`原始指令 0：命中 1，傷害 47`,證實**這段公式已經寫進 remake 且可執行到底**(下面幾行 IDs24/28/29/31 等的 raw formula 有被實際呼叫到)。**但這是 remake 自己的截圖,不是跟真正原版 EXE 對照**——目前沒有 hash 對得上參考版本的 FD2.EXE 可以跑起來做真原版即時比對(見 `docs/data/fd2-reference-files.json` 稽核),所以「UI 已接」只代表 remake 程式碼路徑走得通,不能宣稱畫面/演出跟原版逐 pixel/逐幀一致 | 高 |
| native IDs17–19 modifier | SDD56 UI-03 | 🟡 raw recompute adapter | 已驗 `+0x22..+0x24` raw writer／duration；`ApplyNativeRuntimeEquipmentRecalc` 已保存 `0x1B750` 的 binary64 1.15、x87朝零、HIT/EV+15與裝備累加。尚未把 phase expiry、command transaction及presentation接成正式玩法；不能把 legacy Buff 視為同一機制 | 高 |
| native IDs20–22、25–27 clear/application | SDD56 UI-03 | 🟢(2026-08-14 訂正:本來就已經接好) | **2026-08-14 更正**:上一版此列(同一天稍早)誤判成「只在測試裡呼叫,沒接指令執行路徑」——那是因為只查了 `ClearNativeUnitByte`(0x22af6 raw byte-array 版)/`ApplyNativeRawApplication`(0x22d1b raw byte-array 版)這兩個底層 primitive 的呼叫端,漏查了更高層、真正被玩法使用的 Unit-based 版本。實際上 `battle.ExecuteNativeCommandClearRestore`(ID20/21)與 `battle.ExecuteNativeCommandApplication`(ID22/26/27)**已經**接在 `cmd/fd2/main.go` 的指令執行 dispatch 裡(`id==20\|\|id==21`、`id==22\|\|id==26\|\|id==27` 分支),包含目標解析(`NativeCommandEffectTargets`)、MP 扣除(`SpendNativeCommandMP`)、傷害/回復公式全部走真正的原生路徑,且逐行核對與 disasm 相符。**新確認的語意**:`ApplyNativeTransientPoisonDamage`(見上「中毒每回合」列)證實 `+0x25`=中毒,而 `ExecuteNativeCommandApplication` 早就把 ID26 綁定到 `+0x25`——也就是說 **ID20(clear +0x25)=解毒、ID26(apply +0x25)=下毒,是同一個狀態的清除/施加對稱指令**。同理 ID21(clear +0x26)/ID27(apply +0x26)也是一組對稱指令。**命名確認(同一天稍晚)**:`docs/data/command_labels.json` 記載 command21="社麻術"(疑為「解痲術」字模誤判)、command27="麻庫術"(疑為「麻痺術」字模誤判)——兩者都指向同一個「麻痺」概念,故 **`+0x26`=麻痺**,跟「會擋自然回血」的旁證一致。ID22(apply +0x27)對照 command22="封咒術",故 **`+0x27`=封咒**;目前沒有找到對應的 clear 指令,可能只能自然歸零解除。新增整合測試 `TestNativeCommand26PoisonLifecycleThroughTickToCommand20Cure`:走真正的 ID26 下毒→camp-phase tick 扣血→ID20 解毒 全流程,`go test` 全綠。**仍缺**:`+0x27` 的 clear 對應指令(如果存在)、以及演出層(道具/技能選中動畫、SFX)。 | 低;`+0x27` clear 對應指令、演出層 |
| native ID23 relocation | SDD56 UI-03 | ⚠️(2026-08-14 排查:卡在目標形狀不同) | raw mutation primitive(`SetNativeUnitCoordinateBytes`=0x22253、`NativeRelocationDestinationAllowed` mode6 legality、`ApplyNativeItemRelocation`)都已存在且對過 disasm，但**沒有 Unit-level 指令執行 wrapper、也沒接 `main.go` dispatch**。卡住的原因不是不知道公式，是這個指令的目標形狀跟其餘所有已接指令(17-35/0/13-16 等)不同——其餘指令都是「解析游標上站著的單位」(`tgt := g.st.UnitAt(g.curX, g.curY)` 餵給 `NativeCommandEffectTargets`)，但傳送術的目的地可能是**空格**，沒有單位可以被 `UnitAt` 解析出來，硬套現有 targeting 模式會做錯。需要新的「選目的地格(可為空)」UI 流程，不是重用既有模式能簡單解決的，故意不做假接線 | 中;新的目的地選格 UI |
| native IDs32–35 compound | SDD56 UI-03 | ❌ | static helper order 已知，但 MP transaction、rollback、UI/SFX 未閉合；禁止以 legacy combo 實作宣稱完成 | 高 |
| 經驗值公式(攻擊/恢復/各系術) | doc02 §4.5 | 🟡 normalized approximation | legacy `growth.go`／`CastArea` 的獎勵不證明 native command 逐 ID 的 EXP route；IDs22/32–35 等仍缺原版 transaction/effect evidence | 高 |
| 升級(每 100 經驗一級、成長亂數) | doc02 §2/§4.6/§7.2 | ✅已補(worklist 第 9 輪) | `growth.go GainExp`/`applyLevelUpGrowth`,門檻 100(doc03 0x43),可連續跨級;`growthTable` 為 doc02 §7.2 顯示值與 EXE 升級成長表(`docs/data/exe_tables/growth.json` 0x55EA1)交叉比對後的精確版(63 列全比對成功,見該檔案頭註解),非估計值。`Unit` 新增 `Exp`/`ExpPerLevel`/`DX` 欄;`ExpPerLevel`(攻擊經驗公式的「守方每級經驗」)來源 EXE 敵/友單位表,由 `export_units.py` 新增 `ex` 欄接上,34 份本機 `map*_units.json` 資產已重新匯出;查無成長資料的單位(如無名雜兵)等級仍照門檻演進但不套用屬性成長,誠實標記非靜默丟棄。**升級是否立即回滿新增 HP**doc 未明講,採較合理的 RPG 慣例並於 `growth.go` 註解誠實標記為假設 | — |
| 敵方 AI：物理落點、尋路與目標評分 | doc11（2026-07-29 recheck） | 🟡(2026-08-14 mode 0 移動 fallback 已接線) | `0x145CD→0x4E040→0x146D1→0x14B16` 已閉合可達落點；`0x14237` 已閉合逐落點／目標評分；`0x14B78→0x4E1A6→0x13488` 已閉合方向碼、地形成本、路徑與實際落點排序。FDFIELD `b17/b18/b19` → runtime `+0x34/+0x35/+0x36` 的來源、33 圖分布及保留高四位的範圍 writer 已資料化。mode 2 已修正為 `0x14EF0` 失敗後 `0x14237→0x13FD4`，不走最近座標；mode 11 的兩個 signed score gates 與唯一已知 runtime writer 亦已閉合。`0x13FD4` 是 raw `+0x25/+0x26` gate 的 `floor(maxHP/5)` 回復，已同步正式休息路徑。一般 mode 0 才會先走 `0x14121` blocked-cell 搜索，再以 `0x13E9C` Manhattan 最近 raw opposite group 備援；舊 `0x15192` 說法撤回。**新完成(2026-08-14)**:mode 0/1/2「原地無立即行動時該往哪移動」的 fallback 都已完整組成並接進 `aiActUnit`:
- mode 0:`0x14121`→`0x13E9C`→`0x13FD4`(`ApplyNativeAIMovementFallback`)
- mode 1:`0x14121`→`0x13FD4`,無最近敵人 fallback(`ApplyNativeAIMode1MovementFallback`)
- mode 2:直接 `0x13FD4`,永遠不移動,只休息(`ApplyNativeAIMode2MovementFallback`,`0x14237` 這個呼叫形態已確認固定回傳 0)
- mode 3:用 `0x12C60` 依 `record+0x35` 的身分值找特定單位並移向其座標;找不到時**直接跳進 mode 0 自己的分支**(反組譯證實是同一段程式碼,不是另外近似),完整走一次 mode 0 三層 fallback(`ApplyNativeAIMode3MovementFallback`)。`0x12C60` 本身也反組譯過:掃過 `record+8==目標身分` 且 `record+5 bit0` 未設(存活/可用)的第一筆記錄
- mode 8:**什麼都不做**——不移動、不休息(`ApplyNativeAIMode8MovementFallback`)。排查過程一度以為反組譯出的跳轉目標(`0x1317d`)是錯的(落在一個不相關函式`0x1300D`的中段),後來核對兩個函式的 prologue 棧框(都是 4 個暫存器 push + `SUB ESP,0xc`)完全一致,確認是編譯器把兩個函式相同的 epilogue 合併共用——不是反組譯錯誤,是合法的 tail-merge。過程中也踩了一次工具坑:用 `tools/disasm_le.py` 對本機 FD2.EXE 做即時交叉核對時得到亂碼,連已知正確的 `0x13a9f` 函式起點都解不出來,判定是這次呼叫方式本身有位址換算 bug,不代表反組譯結論有問題
- mode 4:不呼叫 `0x14EF0`,直接把 `record+0x35/+0x36` 當固定目的座標交給 `0x14B78`(`ApplyNativeAIMode4MovementFallback`)。手動逐一核對過堆疊 push 順序(`EDI`=selector、`ESI`=actor、`[ESP+8]`→record+0x36、`[ESP+0x10]`→record+0x35,對照 0x14B78 已確認的 X 最後 push 慣例)才敢下結論,事後跟 doc11 既有記載(這條規則本來就有,只是先前沒讀到)完全吻合
- mode 7:移向 `record+0x35/+0x36`,精確抵達該格時把 `record+5` 整個寫成 1(停用,`ApplyNativeAIMode7MovementFallback`)
- mode 9:用 `0x12C60` 依 `record+0x35` 身分找單位並移向;找不到時**不猜**,直接 `ok=false` 回到一般 `0x14EF0` 路線(doc11 原文如此,跟 mode 3「找不到回 mode 0」不同,不可混用),`ApplyNativeAIMode9MovementFallback`
- mode 10:先走 `0x14EF0`(呼叫端已處理),失敗改移向 `record+0x35/+0x36`,跟 mode 4 同一個座標公式但不做 mode 7 的抵達停用(`ApplyNativeAIMode10MovementFallback`)
- mode 5(部分):`+0x3D` 事件已觸發(`State.NativeEventState[+0x3D]!=0`,即原生 `[0x53AD5+event_id]`)時與 mode 1 同構(`0x14121`→`0x13FD4`);尚未觸發時需要新的 FDSHAP 寶箱旗標格 × event_id 資料表(`0x15DF3` 掃描邏輯已反組譯,但尚未從 33 圖抽取成可查表資料),此分支保持 `ok=false`(`ApplyNativeAIMode5MovementFallback`)。反組譯過程中發現 `docs/data/fd2_ai_mode_dispatch_disasm.txt` 的位址全部屬於已遺失的舊版 EXE,不能直接套用到新版即時反組譯(位移量非模組級常數);詳見 doc11 的專節記錄

逐行核對 `0x14121` 本體反組譯後修正了一個理解錯誤:找到的座標不是直接落點,是餵給 `0x14B78` 正常尋路的「意圖座標」,已用既有的 `Reachable`+`SelectNativeMovementDestination` 組合重現這層間接,不是直接 teleport 到目標格(那樣會疊到敵人身上)。**新增了單位自己 mode 值(`record+0x34&0xf`)的檢查**——一開始漏了這個檢查,對所有單位無條件套用 mode 0 邏輯,是真的 bug;33 張地圖實測分布 mode 0=1063(56%)、1=34、2=535(28%)、3=78(4%)、4=34、5=41、7=4、8=90(5%)、9=2、10=6,現在 mode 0/1/2/3/4/7/8/9/10 九個分支合計覆蓋約 97.8%(1846/1887)有 raw provenance 的 AI 單位;mode 5 的「已觸發」子分支再補進來後,實務覆蓋率會更高(取決於戰鬥中該 41 個單位各自的事件是否已在別處觸發)。單元測試過程中抓到並修正兩個真實 bug(測試 fixture 缺 `OnField` 導致誤判無人佔格、`NativeRecordWord42` 沒同步 `MaxHP` 導致回復量算錯)。缺 raw provenance 或 mode 5「尚未觸發」分支的單位自動退回舊的最近可達格近似,不 regress 現有章節。**仍未做**的是所有 mode 共用的「原地是否已有可攻擊目標」三分數(物理/法術/道具)決策與執行(`0x14EF0`),以及 mode 5「尚未觸發」分支所需的 FDSHAP 寶箱旗標格資料抽取——`0x14EF0` 這塊的量級遠大於已完成的移動 fallback。`0x1DEBE/+8`、完整 mode/selector/turn 語意與 production runtime 接線仍未閉合。**2026-08-14 追加進度**:`0x1DEBE(actor,x,y)` 已補上 Go 實作(`NativeAI1DEBEAdjacencyGate`);交叉核對既有 `ApplyNativeEquipmentRecalc`(`record+0x48/+0x4A`=AP/DP)與本次 mode0/1 fallback 已用過的 `record+0x40`=HP,確認 `0x14237` 物理評分公式即「actor AP−target DP,若嚴格>target 目前HP 則翻倍」;**首度對新版 EXE 即時反組譯 `0x14EF0` 本體**(見 doc11 專節與 [`fd2_ai_14ef0_dispatch_disasm_2026-08-14.txt`](../data/fd2_ai_14ef0_dispatch_disasm_2026-08-14.txt)),完整三分數比較/tie-break/三個執行分派目標開頭均已確認,`ScoreNativeAI1598A`(法術)、`ScoreNativeAI1567E`(道具)兩條評分管線本身已完整可用；**2026-08-14 訂正**:上面「地形百分比表數值萃取不出來」的判斷是錯的——裝 Docker+建 dosbox-x
花一輪挖出 live memory 數值後才發現 `remake/internal/battle/terrain.go` 的
`NativeTerrainAPDPPct`(`0x1acf3` 索引 `0x51a12`/`0x51a2a`)早就有這張六筆表,而且**已經接進
`combat.go` 的 `AttackWithRNG`/`estDamage`**,不是資料缺口。這輪的真實新增價值只有:(1)三個
獨立來源(舊 disasm、live memory、遊戲內 UI 實測)第一次同時確認同一張表,信心度更高;
(2)一套可重用的 DOSBox-X live memory 萃取方法論(存進使用者記憶,doc11 有完整記錄)。
新加的重複 Go 檔案已刪除。**教訓已記錄**:下次判斷「資料缺口」前要先查
`remake/internal/*/*.go` 有沒有現成實作,不能只查 `docs/`。

**2026-08-14 native-accurate `0x14237` composer 完成**:反組譯出目標索引陣列產生器
`0x39a2c`(純 Manhattan 距離+raw 陣營碼,跟法術/道具用的 `0x14818` 是不同函式,新增
`NativeAIPhysicalAttackTargets`)後,`battle.ScoreNativeAI14237` 把裝備武器查詢→
`NativeAIPhysicalDestinations`(候選落點,budget 用 actor 自己的 `record+0x3B`,不是
固定 28)→地形修正(`0x44397`=舊版 `0x1F183` 同一顆閘門函式,新版位址反組譯確認)→
`NativeAIPhysicalAttackTargets`(目標枚舉)→`ScoreNativePhysicalAttackCandidate`+
`SelectNativePhysicalAttackCandidate`(priority/`0x1DEBE`/raw`+8`全部串好)組成一個
完整函式,含端到端測試(含 1DEBE 加成+raw+8 乘數同時觸發的完整公式路徑)。
**2026-08-14 已接線+live 驗證**:`ScoreNativeAI14237` 已 fail-closed 並聯進真正驅動
`cmd/fd2` 敵方回合的 `combat.go` `NextAIPlan()`(確認 `aiActUnit` 是死碼,`cmd/fd2` 從未
呼叫它,只有測試在用;為保留邏輯對稱性也順手接了 `aiActUnit` 頭部,但無實際效果)。
`go build/vet/test ./...` 全綠,零回歸。用 `FD2_CAMPAIGN=1 FD2_CAMP_PREP_BATTLE=
battle_ch01 FD2_SHOT_AI=1 FD2_SHOT_TURN=1` 實跑 ch01 真實戰鬥驗證,發現一個**跟這次
接線工作無關的既有資料缺口**:`NativeAIScoringRecords` 要求 roster 裡每個單位都有
`NativeRecordByte34/35/36`+`Word42/46`,而玩家隊伍 4 名角色(經
`internal/campaign` 加入/延續路徑構造)這五個欄位全缺,敵方(直接讀
`map0_units.json`,本身就含這些欄位)則齊全——導致 `NativeAIScoringRecords` 對整個
roster 回傳錯誤,`ScoreNativeAI14237` 目前在真正戰鬥中**還沒機會觸發**(不是接線
bug,是 fail-closed 正確地退回 `aiTargets` 近似)。詳見 doc11 對應段落。與物理/法術/
道具**執行**(套用效果,非評分)三條獨立鏈路一樣,執行端都還沒做 | 中;
**2026-08-15 已補上**:玩家角色 byte34/35/36/word42/46 缺口已用 Ghidra 靜態反組譯
確認+修正(見 doc11 對應段落)——`record+0x34/35/36` 是 FDFIELD 部署建構器專屬、
只有從不對 Own 執行的 `0x13A9F` 讀取,證實 0 對玩家單位無害;`+0x42/+0x46` 證實
就是 MaxHP/MaxMP。已補進 `event.go PartyUnits`/`native_join_constructor.go`/
`native_persistent_party.go` 三個新單位建構點,live 驗證確認 `NativeAIScoringRecords`
不再對整個 roster 報錯。**mode 5 尚未觸發分支已於同日補上**——原以為需要新抽取地圖
資料,實際上 `State.Treasures`(`tools/sync_native_treasures.py` 產生的逐格
treasure_slots/treasure_hidden,`battle.Load` 時已 join 好)早就是這份資料,只是沒
接進 `ApplyNativeAIMode5MovementFallback`,見 doc11 對應段落。物理執行鏈中度信心判斷已被
既有 `NextAIPlan`/`AttackWithRNG` 接線覆蓋(未 100% 端到端證實)。**2026-08-15 道具執行鏈
(`0x3A269`)深入偵察**:完整追出 call chain 結構(混用靜態 LE 反組譯+DOSBox-X live 記憶體
讀 overlay 區),確認後半段幾乎全是朝向計算/screen blit/timer delay 等演出邏輯,已逐一排除
非效果來源,追到尾端 `0x45E83` 這個共用效果核心——**重大發現:`0x45E83` 同時是道具與
法術執行鏈的共用效果套用系統**(函式開頭/結尾分別呼叫法術鏈早就記過的 `0x426DF`/
`0x4270A` jump table,證實兩條執行鏈匯流進同一套機制,不是各自獨立)。已定位 20 個
kind 分支各自的呼叫目標(完整表見 doc11)。**⚠️ 2026-08-15 重大修正**:原本以為這些
kind 的效果公式是新發現,查核後發現**其中至少 9 個(5,0xd,6,7,8,9,0xa,0xb,0xc,0xf,
0x10,0xe,0x16)在更早的 session 就已經反組譯+實作+測試完成**,存在
`remake/internal/battle/native_raw_*.go`(舊版位址編號:`0x1c916`/`0x1c81f`/`0x1c9dd`/
`0x22997`/`0x22721`/`0x22866`/`0x22af6`/`0x22d1b`),這輪是重工,見 doc11 的完整
新舊位址對照跟修正說明。**真正的缺口不是效果公式**(已完成),**是接線**:
1) `combat.go NextAIPlan` 從未讓 AI 真的選擇施法(`SpellID` 全部寫死 `-1`),即使
`ExecuteNativeCommand*` 系列已經能透過玩家 `confirm()` 正常施法;2) 道具側連玩家都
沒接——`native_item_*.go` 的 6 組 `RouteForType`+`Apply*` 完全沒有呼叫端,需要新建
一個頂層 dispatcher。3 個機制證實語意未定(0x11,0x12,0x13)、1 個結構不同未追(0x17)
是這輪唯一站得住腳的新發現。見
`docs/data/fd2_ai_item_exec_3a269_disasm_2026-08-15.txt`(現 1400+ 行)完整證據 |
| 敵方 AI:**施法決策**(法師/僧侶主動用攻擊術/補血術) | direct disasm 證實兩條不同 producer：`0x1567E` 枚舉 inventory slot→item row command，候選交 `0x15880`；`0x1598A` 枚舉 unit command mask，候選交 `0x15B77`。兩條 producer 均已有具型別實作；前者 command>0x0F 才做 `command-0x10`，兩套 ranking 不可合併 | 🟡 | `BuildNativeAIPhaseDiagnosticPlan` 已依原序計算兩個分數；`ExecuteNativePhaseUnitScans` 另保存逐筆重判、90／30 筆回呼順序與 pending 提前退出。**2026-08-14 訂正**:doc42 舊敘述「`0x13A9F`...仍未接入」容易誤讀成「還沒反組譯」——實際上 doc11 已把 `0x13A9F`(size 1021,unit-action mode dispatcher,讀 `record+0x34&0xf` 選分支)幾乎每個 mode(0/1/2/3/4/5/7/8/9)對應的原生函式都個別記載過(`0x14EF0`/`0x14121`/`0x13E9C`/`0x14237`/`0x12C60`/`0x14B78`/`0x13FD4`/`0x15DF3`/`0x1BB8C`/`0x32975`...),連「下一步最小驗證」的具體步驟都寫好了。真正缺的是**把這些已知的 mode 分支各自組成 Go 版執行器,取代 `aiActUnit` 目前的「往最近目標移動,範圍內就打」簡化邏輯**——這是一個跟前面指令接線完全不同量級的工程(要覆蓋 9+ 個 mode 分支、兩遍掃描結構、`[0x51A8F]`/`[0x53C03]` 章節事件 dispatch),不是漏了一個 case 而已 | 高；把已知 mode 分支組成完整 AI 執行器(大工程,非小接線) |
| 敵方 AI:**使用道具** | `0x1567E→0x15880` 已證實會依 raw inventory slot 與 item row command 做預選；這證明 AI 有物品指令候選，不等於每種道具效果都已命名或可執行 | 🟡（僅靜態預選） | `ScoreNativeAI1567E` 已閉合數值 producer；`aiActUnit` 尚未接物品交易、消耗、效果與呈現，故正式執行仍維持失敗即關閉 | 高；補執行消費端、物品交易及同狀態原版驗證 |
| 移動地形成本(依「單位所屬 class」分開算) | doc11(`0x14B78→0x4E555`)、`56` SDD(`0x4e555(selector)` provenance) | ✅(2026-08-14 補完,取代舊的步行/騎兵/飛行三分類猜測) | 原版**不是**簡單的步行/騎兵/飛行三分類——`0x4e555(selector)` 是一張**29×20 的逐 class 成本表**(`docs/data/exe_tables/native_movement_cost_rows.json`,已入庫 `remake/assets/data/`),`selector` 已由 doc11 兩處獨立 call site(AI 移動 `0x14B78`、道具傳送 `0x115b6` mode6)交叉證實 = 目標的 class(`record+0x20`),`record+8==0x1c` 時強制改用 row1。`move.go` 新增 `State.NativeMovementCostRows` + `nativeMoveCost()`:selector=`u.ClassID`(或 `u.HasNativeRecordByte8&&u.NativeRecordByte8==0x1c` 時=1),column=已證實的 `NativeTerrainMoveCodes`,row 值 ≥20 視為這個 class 走不進去(對齊 `NativeRelocationDestinationAllowed` 既有的 `==20` 判斷)。`MoveCostFor` 優先用這條原生路徑,查不到資料才退回舊的 `MoveType` 三分類近似(現在變成純相容 fallback,不再是主要機制)。**2026-08-14 已補完第三種例外**:玩家提供「新版」基準版 FD2.EXE 的 Ghidra 反組譯,逐行核對 `0x14B78`(選 row 的呼叫端)與 `0x1F183`(predicate 本身)兩個函式,確認選擇順序是 class(預設)→`0x1F183`成立則 row19 →`record+8==0x1C`成立則 row1(檢查順序在後,同時成立時 row1 蓋過 row19);`0x1F183` = `record+0x20==0x13` 或 `record+0x1F(race) in {4,5}`,`record+7==0x1C` 時整個 predicate 直接 false。已寫入 `nativeMovementRow19Predicate`+`nativeMoveCost`(`move.go`),`go test` 全綠。唯一保留的已知局限:`record+7` 這個閘門 byte 目前沒有任何匯出管線填值,故意不建模而非用 0 假設它一定不是 0x1C——影響範圍是「少數本該被抑制的單位多套用一次 row19」,比先前完全不套用還窄。 | — |
| **地形攻防加成** | native `0x1acf3`、`0x51a12/0x51a2a` | ✅原版逐格資料 | 同上「物理攻擊:地形 AP/DP% 修正」條：完整 raw map 直接用 FDSHAP control byte+1；0→(+5,0)、1/5→(0,0)、2/3→(-5,+10)、4→(-5,-5)。這取代 doc02 對一般地面 DP-5 的舊摘要；Cost 僅是 legacy fallback。 | 低 |
| 裝備欄 / 裝備加成 AP/DP/HIT/EV | doc02 §5、doc32 §1/§5 | 🟡 | `Unit` 有 `Inventory`/`Equipped`/`InventorySlots`；`campaign.EquipItem`、`RecomputeEquipment` 與 shop equip UI 已接線。HIT/EV 真值與戰鬥全鏈仍需對照原版欄位，不能再說「無裝備欄」 | 高；補 native stat source 與 battle integration |
| 道具使用效果(藥水回血、卷軸) | doc02 §5.13、doc32 | ✅(2026-08-14 用 remake 重新核對,取代舊❌) | 這行舊敘述已過期——`native_item_panel_ui.go` 的 `applyNativeImmediateItem`/`beginNativeTargetItem` 其實已經是完整功能。用 `FD2_ORIGINAL_FDOTHER/FDTXT/DATO` 指到玩家本機原版檔案(內含真實道具資料表)、跑 remake 截圖確認:永久屬性藥水(ID198「力量藥水」,doc32 type8/9/0xa)使用後 `AP:016→025`(剛好+9,對齊 doc32 已記錄的公式)、正確從欄位移除、訊息顯示「原始效果完成」;需選目標的回血藥水(ID196,doc32 type6/7)正確進入「選擇目標」階段、消耗來源槽延後到確認後才執行。新增 `FD2_SHOT_ITEM_FORCE=<id>`/`FD2_SHOT_ITEM_CONFIRM=1` 除錯開關(跟其餘 `FD2_SHOT_*` 同一套模式),不需要真的練等/找到該道具即可測試任何道具 ID。**釐清證據等級**:這裡驗證的是「remake 讀取玩家本機真實道具數值表、依 doc32 已記錄的公式算出的結果，數字對得上」，不是「remake 畫面跟原版 EXE 跑出來的畫面比對」——後者目前做不到,因為手上沒有 hash 對得上參考版本的 FD2.EXE 可以實際執行(見 `docs/data/fd2-reference-files.json` 稽核)。仍待驗證的是其餘 doc32 記載的 item type(如卷軸類 type12/14/15/16/22/23)跟原生演出(indexed presentation)。 | 低;其餘 item type 逐一核對 |
| 裝備自帶法術(不耗MP、無經驗) | doc02 §4.6、doc32 | 🟡 | 裝備資料與裝備重算已存在，裝備法術在 `Cast`/action menu 尚未接成獨立不耗 MP 路徑 | 中 |
| 轉職系統(Lv20+教會、轉職道具→最高職業) | doc02 §7.1、doc32 §4「[阻] 轉職系統」；official IDA `0x31385/0x31793/0x311DC/0x19953` | 🟡 | `church` UI、`ClassChangeCandidates`、單一 target resolution（special>optional>default）、Yes/No confirmation、`ApplyClassChange` 與 growth table 已存在；exact indexed renderer、fee／數值實機差分仍待 | 中 |
| legacy 中毒/麻痺/封咒與 Buff 的回合處理 | doc02 §6.4 | 🟡(2026-08-14 大幅補完) normalized approximation 仍並行 | `model.go TickStatus`/`main.go completeTurn()` 仍在跑,但同一函式現已額外接上 native 路徑:`battle.NativeCampPhaseOwnRegen()`(own-camp 自然回血)、`ApplyNativeTransientPoisonDamage(selector)`(中毒扣血)、`TickNativeTransientsRaw(selector)`(逐 byte 遞減),依 Ghidra 反組譯證實的呼叫序 own regen→selector1→selector0→selector2 執行。**新確認**:`0x1A866` 三個呼叫點(`0x1A4D1/0x1A55E/0x1A797`)全部位於同一函式 `0x1A30B` 內部,不是分散的獨立 caller(修正 doc56 舊誤述);`0x1A30B` 本身是「每回合結束一次」的原生 orchestrator,不是逐 camp 各自觸發。目前所有地圖資產 `native_transient` 皆全零,這段接線現況無副作用,等 native command 執行路徑開始寫值才會顯現效果。仍缺:歸零時的 expiry 訊息／`0x1B750` 重算尚未接(見下兩行),`+0x22/+0x23/+0x24/+0x26/+0x27` 五個 index 語意仍未命名(僅知 `+0x26` 會擋 own regen) | 高（expiry 訊息/重算接線、其餘 5 個 index 命名） |
| legacy 中毒每回合 −10% HP | doc02 §6.4 | ✅(2026-08-14 補完,取代舊 🟡) | `TickStatus` 的 `dmg := u.MaxHP/10` 公式本身完全正確——Ghidra 反組譯證實 `0x1A866` 第一個迴圈(decrement 迴圈之前,獨立的一次掃描)對 `record+0x25`(=`NativeTransient` 陣列 index 3)非零的單位套用完全相同公式,且不遞減該 byte。已寫入 `battle.ApplyNativeTransientPoisonDamage`,`NativeTransientPoisonIndex=3` 常數,單元測試涵蓋 clamp/gate。**命名確認**:`docs/data/command_labels.json`(既有反組譯證據,FDTXT_000/`0x1ceed→0x15f84`)記載 command20="解毒術"、command26="毒擊術",兩者皆綁定 `+0x25`——跟今天從 `0x1A866` 獨立推出的「+0x25=中毒」公式面證據完全吻合,雙重印證。 | — |
| legacy Buff(魔刃/魔鎧/風行)到期清除 | doc02 §6.4 | 🟡(2026-08-14 施放端已接) normalized approximation 仍並行 | `TickStatus` 的共享 `BuffTurns` 歸零清空仍在跑；**新接**:`battle.ExecuteNativeCommandModifier`(ID17="魔刃術"/AP、ID18="魔鎧術"/DP、ID19="風行術"/HIT+EV,名稱來源 `docs/data/command_labels.json`)已實作施放端(目標解析、MP 扣除、`+0x22/+0x23/+0x24` 寫入 duration、`trunc(current*0.15+1)` 增幅 AP/DP、HIT/EV 各 +15,逐行核對 `0x22721/0x22866` 公式相符),已接進 `main.go` 的 `id==17\|\|18\|\|19` 分支,單元測試涵蓋三個 ID 與已啟用跳過。**故意不做**的是到期移除:原版靠 `0x1A866` 歸零後呼叫 `0x1B750` 從 base+裝備整個重算,不是減回同一個 delta——這個引擎目前沒有 Unit-level 的裝備重算橋接(`ApplyNativeRuntimeEquipmentRecalc` 只吃 raw `[]byte`+itemTable,不吃 `*Unit`),硬做一個「到期就減回同樣 delta」的近似會在裝備/其他 buff 變動時跟原版真正的行為不一致,所以誠實地不做,留到裝備重算橋接完成後再補。ID34(破壞神)目前借用 legacy `applyBuff` 湊出四合一效果,不是真正的 native 逐 ID 實作 | 高;Unit-level 裝備重算橋接、到期移除 |
| 對話嘴型動畫(m0閉/m3開,doc14 0x16d00) | doc14、doc40 | 🟡 | `main.go`/`internal/dato.MouthState` 已對齊每 2 frame、開嘴 1 tick、`rand()%30+2` cadence，並可載入四幀 DATO；但 `0x168b6` dialogue-frame/grid、完整 resource binding、speaker layout 與 runtime dialogue parity 尚未閉合，不能列為完整 ✅ | 中 |
| 法術施放演出(命中/傷害畫面) | doc35、doc37 | 🟡 approximation | remake 攻擊型法術(`sp.Target==0`)重用 `newAtkAnim`，治療型只有文字；這是目前 runtime 缺口，**不是原版「無獨立法術特效」的結論**。原版僅證實 `0x28784` 不以 spell-id 選另一段 FIGANI；`0x2a6bd` command presentation dispatcher 與命中／效果層仍待閉合。 | 中(補 native presentation/effect path) |
| 商店(一般商品) | `0x2e341→0x2f0b0/0x2f642/0x2f883/0x2f8ea`、doc56 UI-09 | 🟡 | purchase、sell、standalone equip與transfer四條production縱切已閉合。ch02 variant1/3/5主選單、weapon purchase-list四個selection、purchase Yes/No、gold0不足金與gold1000裝備收件者selection0/cycle1已有全幀DOSBox E2；該recipient E2仍使用screenshot-only bootstrap。正常campaign已另修JOIN→LOADCH首次typed roster seeding，ch00 scenario/order可進ch02候選`[0,9,4]`，direct replay不造persistent state；這是runtime regression，不是native FD2.SAV或完整playthrough E2。transfer保存512/511/510/506訊息、source/item/destination/full loop、raw remove→append→source recalc與self-transfer。sell仍只宣稱gameplay parity，不宣稱save byte parity；custom variant0保留generic fallback | 高；補recipient input/scroll、no-recipient/full/success、sell/equip/transfer與其他章節同狀態E2 |
| 城鎮hub畫面／selector | `0x2cd16/0x2cf71/0x11eb0`、FDOTHER#10/#11/#61/#62、FDTXT `0x1ef+selection`、FDICON0..2 | 🟡 production／ch02 variant0 E2 | 23個town保存raw variant0/1/2；production已接原版背景、label、六組座標、`0,1,2,1` pulse與312×192→VGA `(4,4)`。ch02 variant0 selection0–5、Left/Right wrap與hidden reveal均有全幀DOSBox E2 | 高；補variant1/2與其他章節capture |
| 祕密商店進入gate | `0x2cde0..0x2cef7`、town table `0x6238d`、`0x2d28c` selection5→`0x2e341` | 🟡 production／ch02 E2 | 撤回舊✅、persistent-flag等價及「chord立即進店」說：原版以每章0x1f-byte record的`+1`目前選項、`+2` BIOS Shift/Ctrl/Alt-F1..F10 scan同時命中，當次只把selection改為5並重畫；後續Enter才dispatch。23筆gate已進editable `native_secret_gate`；ch02 chord→confirm→variant5與Escape return已有DOSBox E2；legacy `SecretIf`／`found_secret_ch*`只保留擴充相容 | 高；其餘22個town逐章chord/route E2 |
| 商店賣出(原價 75 折) | doc02 §4.6、native shop callee audit | 🟡 | `campInput` shop sell mode、`campaign.SellSlot`、price×3/4 與 inventory/equipment recompute 已實作；這只證明 normalized transaction，原版 service callee、indexed menu/cancel semantics尚未閉合 | 中 |
| 存檔/讀檔 | doc19、doc56 UI-12 | 🟡（自有格式；原生匯入部分完成） | `save.go`保存campaign節點／旗標／金幣／道具／typed persistent party與deploy/order；四槽 bounded selector 與原版 indexed compositor 已接，空槽達 E2，修改存檔有效槽只作排版 oracle。`FD2_NATIVE_SAVE` 可驗 checksum、顯示四槽 metadata，並對空槽／未支援還原的有效槽保持 selector；仍缺 native roster→normalized party、一般玩家成功 restore 與完整 playthrough，不能標成原版機制✅ | 高 |
| BGM 播放 | doc12 | ✅ | `audio.go playBGM`,同曲不重播/換曲釋放語意對齊 `0x26777` | — |
| SFX(命中/陣亡/選單音) | doc36 | ✅(池對照為近似值,doc36 已註記真實 attack_id→sfx 池對照未 RE 完成) | `audio.go loadSFX/playSFX`,`main.go` 多處呼叫 | — |
| 出場人數上限(前27章16人/末3章20人) | doc02 §4.6、native `0x2d093→0x318ad` | 🟡 | remake 已把可選人數門檻資料化為一般 `party_limit=15`、末路線 `party_limit=19`；外層已證實小名冊完全略過選人，超過門檻才進全零勾選表。這是 native 0-based cap 的目前證據，不把持久記錄總數16/20與可選上限15/19混為同一欄。仍待完整 native deployment cursor／overflow 行為與實機 UI 對照 | 中 |

## RE 側也需要補的缺口(非 remake 落差,附帶記錄)

- **施法入口已找到，但 producer 必須分開**：`0x154D1` 仍不是入口；
  `0x1567E→0x15880` 是 inventory item-command 預選，
  `0x1598A→0x15B77` 是 unit command-mask 預選；`0x15055/0x150F1`
  是執行消費端。兩者不能共用未證實的 ranking 或槽／command 身分。
- **doc32 §4 三個 `[阻]` 項目(裝備加成精確公式、物品使用效果碼、轉職系統機制)本身就還沒反組譯完**,remake 的裝備/道具/轉職缺口有一部分要等 RE 補完才能對照實作,不能單純算「remake 沒做」。

## 已移除的歷史統計與排序

早期的 33 項計數、worklist 第 8 輪增減帳與「前 5 項」排序已被後續程式與 RE 證據取代，
會與上方逐列現況互相矛盾，故不保留在本文件。需要歷史 provenance 請查 Git；當前優先序
由 `56` SDD 的 evidence gate、`57` UI matrix 與 `91` worklist 決定。
