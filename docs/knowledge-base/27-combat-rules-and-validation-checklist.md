# 27 — 重製戰鬥規則來源 + 需動態實機驗證清單

> 回答三件事:(1) remake 新需求「回合無上限」;(2) 青衫攻略公式對重製的作用;(3) 哪些只能靠**動態實機(DOSBox)驗證**——靜態反組譯到頂的項目清單。
> 原則:能用「攻略公式 + EXE 數值表 + 靜態反組譯」確定的,就不動態;只有三者都無法定論的才列入動態驗證(省成本,對齊 rulebook 62「動態是末段」)。

## 1. 新需求:remake 回合數無上限(除非劇本限制)

- **原版**:`[0x53bef]` 回合數無硬上限;`[0x53ec8]`(累積計數)有 `clamp 99`,但那不是回合(doc 26)。
- **remake 需求(本輪新增)**:戰鬥回合**不設上限**;只有當該關劇本明確設定「回合限制事件」(如 `turn>=N → 敗北/撤退`)時才受限。
- 落地:M1 戰棋核心的 `BattleState.turn` 用無界整數;回合限制改由 campaign 事件(`when turn>=N → lose/event`,對映 doc 26 `[0x53bef]` cmp N 機制)表達,而非引擎寫死上限。
- 已記入 worklist M1。

## 2. 青衫攻略公式對重製的作用:**有,且關鍵**

青衫 `notes.md` 的戰鬥/經驗公式(整理於 doc 02 §4)對重製有**雙重作用**:

1. **直接實作依據**:傷害、命中、暴擊、經驗、成長公式可**直接寫進引擎**,免去從反組譯一條條推導數值規則。
2. **反組譯交叉驗證基準**:反組譯戰鬥碼(0x18890 等)時,拿公式當預期值對照,確認反組譯正確(已部分對上——doc 11 AI 的 `AP×地形% − DP×地形%` 正是 §4.1 物理傷害)。

**攻略已給、可直接用(不需動態驗證)**:
- 物理傷害:`max = AP×(1+攻方地形AP%) − DP×(1+守方地形DP%)`;暴擊 `DP/2`;`實際 = max×0.9 ~ max−1`(亂數);命中 `(攻方HIT − 守方EV)%`
- 劍技:`AP×劍技加乘`,命中 100%(恆中)
- 法術:`法術最大 ×(1−守方魔抗)`,命中=法術內定
- 恢復:`最大恢復 ×0.9 ~ 最大恢復−1`
- 經驗值(攻擊/恢復/各輔助術,doc 02 §4.5);升級每 100 經驗一級
- 規則:轉職 Lv20+/滿 40、賣價 75 折、升級成長亂數、**出場人數前27章16人/末3章20人**(印證 `[0x53bf7]` 32 槽我方名冊)

→ 這些是數值與公式 baseline；完整戰鬥仍需 native command inventory、target selector、item action、AI spell runtime 與 UI input 的 E0/E1/E2 驗證，不能宣稱只靠表格即可完成。

## 3. 需動態驗證的清單 —— 經使用者領域知識,**多數已定案**(2026-06-28)

原以為要 DOSBox 跑的項目,使用者(熟悉本作)直接給了答案,動態驗證需求大幅降低:

| # | 項目 | 結論 |
|---|---|---|
| 1 | 單位 `byte[+5] bit0` | ◐ **raw caller-specific mask**：已觀察 constructor `0x10eed` 寫0、HP0 路徑 `0x1dc61/0x1dd4c` 寫1、`0x32975` 覆寫1；不能把這些 writer 合併成全域死亡/存活欄位。 |
| 2 | `byte[+5] bit7(0x80)` | ◐ **raw caller-specific mask**：已觀察 bit7 writer/test，但尚未證明所有指令完成都共用此欄位；不得直接命名成已行動。 |
| 4 | `[0x53bef]` 回合遞增 | ◐ **只證實有 increment/compare counter**；我方/敵方 phase 完成條件尚未由完整 state-machine E0 閉合，不採用使用者記憶作原版定案。 |
| 7–8 | 暴擊率 / 地形修正率 / 成長亂數 | ✅ **用青衫攻略數值**(doc 02 §3/§4),不需動態。[使用者確認] |
| 3 | `[0x53ec8]` 累積計數 | ◐ 仍不確定。靜態追到「累加單位欄位 `+0x21` 之值,`clamp 99`」(0x1c81f 函式)。**非重製核心**(回合用 `[0x53bef]`、戰鬥用公式)→ 降為低優先 / 可選,不阻塞。 |
| 5–6 | 章節↔地圖、unit idx→角色 | normalized campaign 可用自有對應；raw handler／LOADCH／acting 路徑仍須保留原版 slot order 與 provenance，不能一概略過。 |
| 9–10 | `roster byte[+8]`、單位完整佈局 | normalized engine 可用自有 `Unit` projection；但 raw persistence／handler path 仍需對齊已證實的 `0x50B` slot、`+8` identity 與必要欄位，不能宣稱整體不需要。 |

→ **結論：領域知識與攻略可作 baseline，但不能清空 raw predicate／回合 state-machine 的 E0 驗證**；`[0x53ec8]` 仍是低優先，
而 byte+5 caller semantics、phase completion 與 native UI 仍需以直接證據逐項閉合。原本的 DOSBox 驗證計畫不可整體取消。

### 已閉合的單位 raw predicates `byte[+5]`
- **bit0** 僅能描述為 caller-specific admission/reject mask：`0x3453e` 回傳 `record+5 & 1`，不能在此文件命名成死亡、隱藏或 inactive。
- **bit7 (0x80)** 僅能描述為 caller-specific test/set/clear mask；`0x32975` 的整 byte overwrite 與 `0x13512` 的 bit7 writer 必須分開追蹤，不能直接命名成已行動或回合完成。
- 重製可用 `Unit` 的 `alive`／`acted` 作 projection，但那是引擎語意，不能當作 native 欄位對映。

> **歷史勘誤(2026-07-16)**：先前依使用者記憶記成「bit0=1 表示存活、初始化=1」，現已由完整反組譯推翻。當時誤把另一個寫1位置當成有效單位 constructor；真正 constructor `0x10eed` 寫0，而 HP=0 的 death 路徑寫1，因此舊定案明確撤回。

## 4. DOSBox 驗證的紀律(host 有 dosbox,但無 debugger)

- 無 source-level debugger → 可用 **DOSBox 內建 debugger 版(`dosbox-x` / debug build)** 的記憶體檢視，或以
  `tools/fd2save.py` 解碼的 **存檔差分** 比對 `FD2.SAV`；其 envelope 已閉合為 rolling-XOR/checksum，record
  欄位仍須以 direct dataflow 命名。記憶體 dump 僅在差分不足以判定 runtime 時序時使用。
- 對齊靜態位址:遊戲在保護模式,linear 位址 = 我們反組譯的 `[0x53xxx]`;DOSBox debugger 可直接看該線性位址。
- 有界、可重現:每項驗證設計成「明確操作 → 觀察特定位址/畫面 → 記錄」,不漫無目的跑(對齊 rulebook 35/64)。
- **截圖 oracle 補充**:行為類(變灰、回合切換、事件觸發畫面)可純看畫面截圖判定,不必讀記憶體(規則 64)。

> 相關:doc 02(攻略公式)· doc 03(EXE 數值表)· doc 11(AI/傷害)· doc 25/26(事件系統/單位結構)· doc 13(戰場選單)。

## 5. 戰鬥演算法反組譯完整性盤點(2026-08-19)

> 回應 worklist 第 245 行(反組譯戰鬥/命中/傷害/AI 演算法,與攻略公式交叉驗證)與第 266 行(反組譯完整性盤點)。
> 方法:純靜態 Ghidra headless(`FD2Analysis3`,唯讀),把 doc58「續二十六」新反組譯出的 `0x2e2b0/0x2ebe1/0x2f7b6`(指令環預設攻擊路徑)與既有多輪已閉合的 `0x1c75e/0x1c81f/0x1c916/0x1c9dd/0x22721/0x22866/0x22997/0x22af6/0x22d1b/0x276ec/0x14237/0x1598A/0x1567E`(命令式法術/道具/AI 路徑)並排,對照攻略公式(doc02 §4)與 remake `remake/internal/battle/*.go` 實作,逐項標記三方狀態。**新增本輪反組譯**:`0x2f7b6` 完整 crit 分支、`0x117e7`/`0x1e292`/`0x1c81f`/`0x1c916` 的 `[0x53ec8]` 經驗值累加/升級鏈(見下表第 13-15 項),修正 doc25/26/35 先前對 `[0x53ec8]` 「presentation value / 語意待定」的錯誤標記。

| # | 項目 | 攻略公式(doc02) | 反組譯位址佐證 | remake 實作 | 三方一致? |
|---|---|---|---|---|---|
| 1 | 物理攻擊基礎傷害 AP−DP | §4.1 | ✓ `0x2f7b6`(續二十六+本輪):`local_1c=(AP-DP)*9/10`,再加 `rand%(local_1c/9)` 的整數變動 | `combat.go:61-66` `max:=ap-dp; dmg:=randomizeAmount(max,rng)` | ✓ 一致(remake 的 0.9~max-1 均勻亂數與 native 的「*9/10 + rand%(除9餘數)」分佈型態相近,非逐位元組相同演算法,標記「近似一致」) |
| 2 | 物理攻擊地形 AP/DP% 修正 | doc11 | ✓ `0x1acf3`/`0x51a12`/`0x51a2a`(先前輪次)+ 本輪確認 `0x2f7b6` 內部經 `0x1f183` gate 呼叫同一張表 | `terrain.go TerrainAPDPPct` | ✓ 一致 |
| 3 | 物理攻擊暴擊(DP÷2) | §4.1 | ✓ **本輪首次 code-level 確認**:`0x2f7b6` 命中判定成立後**另一次獨立** RNG(`FUN_0004ebe3`)、`roll%100<local_2c`(`local_2c`=職業暴擊率表 `DAT_000524a7`=doc32 本輪驗證的 `0x774BC`,可再被武器 type4 加成)才 `DP/=2`;先前 doc42 標「✅」只是 `resist_crit.json` 數值層級比對,非此函式的 code-level 證據 | `combat.go` crit 獨立於 hit roll,`dp/=2` | ✓ 一致,本輪把「✅」從 data-level 補到 code-level |
| 4 | 物理攻擊命中率 (HIT−EV)% | §4.1 | ✓ `0x2f7b6`(續二十六):`(uint)HIT-(uint)EV` 下溢 → reinterpret 成負數 → 恆 miss | `combat.go rollsHitPct`:`pct<=0→false` | ✓ 完全一致(remake 提前預判到這個 native unsigned 下溢行為) |
| 5 | 武器命中後特殊效果(狀態附加/固定暴擊加成/未命名旗標) | 攻略未記載 | **本輪新發現**(`0x2f7b6` 內 `cVar4` 分支,來源 `FUN_0004e8bc()` 疑似武器/物品表 row,`+9`=type、`+10`=強度值):type4=固定加成暴擊率(`local_2c+=uVar9`);type2=命中後對目標套用 `+0x25` 狀態欄(值 2~5 其中一種,疑似異常狀態變體,且消耗一次額外 RNG);type3=設 `param_3[4]` 旗標(語意未定);type0/預設=無特殊效果 | ✗ 無對應機制(僅資料表 crit%,無武器 on-hit 狀態/加成) | ✗ **不一致——原生獨有機制,攻略未記載、remake 未實作,列入仍缺清單** |
| 6 | 劍技傷害 AP×加乘率−DP | §4.2 | ✓ `0x276ec`(先前輪次已閉合):`trunc(actorAP*multiplier/10)-DP`,倍率 15/20/12/18 對應 command 24/28/29/31 | `native_command24.go ResolveNativeCommandDerivedStrikeDamage` | ✓ 一致 |
| 7 | 法術/道具傷害 dmg×(1−魔抗) | §4.3 | ✓ `0x1c75e→0x1c81f`(先前輪次):`base=recordDmg*resist_raw/10`;`resist_raw` 表(`word_51f96`,loaded-view `0x51d96`)與 doc32 本輪驗證的職業魔法抗性表 `0x76FAA` 交叉核對一致 | `native_command_damage.go ResolveNativeCommandDamage` | ✓ 一致,本輪補上魔抗表↔resist_raw 表的交叉確認 |
| 8 | 法術/道具命中率(內定命中率) | §4.3 | ✓ `0x1c7ed`→`0x4e893`:`RNG%100<record[+2]`(先前輪次) | `magic.go rollsHit`(spell.json hit 欄;hit=0 視為必中) | ◐ 部分一致——native 是「`rng%100<hit值`」通用機制,remake 對 `hit=0` 取特例必中(因 spell.json dump 值與攻略「劍技恆中/輔助 50%」矛盾);本輪未逐 ID 用 `record[+2]` 實際數值核對 spell.json 的 hit 欄,**仍缺** |
| 9 | 恢復法術(HP) | §4.4 | ✓ `0x1c916`(先前輪次已閉合):90~99.9% 隨機化 | `native_item_hp_restore.go`/`magic.go randomizeAmount` | ✓ 一致 |
| 10 | 恢復法術(MP) | 攻略未單列 | ✓ `0x1c9dd`(先前輪次) | `native_command_mp.go` | ✓ 一致(無獨立攻略公式列,沿用同一套 randomize) |
| 11 | 輔助法術(魔刃 AP+15%/魔鎧 DP+15%/風行 HIT+15,EV+15) | §6.4 | ✓ `0x22721`/`0x22866`/`0x22997`(先前輪次) | `magic.go applySpell` buff 分支 | ✓ 一致 |
| 12 | 狀態清除/施加(解毒/麻痺/封咒等) | §6.4 | ✓ `0x22af6`(clear)/`0x22d1b`(apply)(先前輪次) | `native_record_flags.go`/`ExecuteNativeCommandClearRestore` | ✓ 一致 |
| 13 | 經驗值—攻擊 | §4.5「(傷害HP/總HP)×(守方等級×守方每級經驗)×(守方等級/攻方等級);致死視同傷害HP=總HP」 | **本輪首次反組譯確認**:`0x2f7b6` 內 `DAT_00053ec8 = 守方等級×ExPerLevel(表[守方+0x7-0x44].+9) / 攻方等級(部分職業 class∈(8,0x19) 或 race==0x1c 時 +0x1e)`;若守方本次未死(`local_24!=0`)再 `×傷害/守方總HP`;若致死則不套用比例(=doc02「致死視同傷害HP=總HP」) | `growth.go AttackExp` | ◐ **高信心新證據,細節與攻略文字有一處落差未解**:攻略公式字面上「守方等級」出現兩次(直接相乘、且在比值裡再一次),反組譯只見一次相乘、一次除以攻方等級(未見守方等級的比值因子);可能是攻略轉錄本身把比例寫得比實際公式複雜,也可能是本輪反組譯遺漏了另一個守方等級因子,**未 100% 排除歧義,不宣告完全 closed** |
| 14 | 經驗值—恢復法術 | §4.5「(40/施法者等級)×Σ(恢復HP/總HP×受法者等級)」 | **本輪新發現**:`0x1c916` 內 `DAT_00053ec8 += 受法者等級(部分職業+0x1e)×40×恢復量/受法者總HP`(gate:`target.+7<0x4b`),`40` 與「受法者等級×恢復比例」都對上攻略公式 | `growth.go` 目前用 normalized 近似(非此 native 公式) | ◐ 新證據但**看不到「÷施法者等級」這個外層除法**——推測可能在下面第 15 項的 `0x1e292` 累加多目標後統一除,也可能攻略轉錄有誤;本輪未追完,**仍缺** |
| 15 | 經驗值累加與升級機制(`[0x53ec8]` 語意) | §4.6「每 100 經驗一級」 | **本輪完整反組譯閉環,修正 doc25/26/27/35 先前「presentation value/語意待定」的錯誤標記**:`0x117e7`(輸入 dispatch)在玩家發動攻擊前 `[0x53ec8]=0`,行動結算後由上列 §13/14 等函式累加,`clamp 99`,再呼叫 `0x1e292(actorIdx)`:`local_18=[0x53ec8]+actor.+0x3c(持久化經驗值 byte);while(local_18>99){actor.+0x21(等級)+=1; local_18-=100; 呼叫0x1b750重算derived AP/DP/HIT/EV(續二十六已證實的同一函式); 若達職業等級上限('c'=99 或 '('=40 等特例byte)則local_18=0}; actor.+0x3c=local_18` | `growth.go GainExp/applyLevelUpGrowth`,門檻 100,可連續跨級 | ✓ **本輪最高價值發現**:完整證實 `+0x3c`=持久化經驗值 byte(先前僅靠 live memory 讀值對上 UI「EX.79」,現在補上 writer/reader code)、升級時重算 derived 屬性用同一個 `0x1b750`,與 remake 邏輯方向(門檻 100、可連續跨級、升級觸發 growth 重算)一致;但 remake 未實作「特定職業等級上限」與「達上限時經驗歸零不累積」這兩條 native 規則,**標記仍缺** |
| 16 | AI 物理攻擊目標評分 | doc11 | ✓✓✓ `0x14237` 完整 composer(多輪已閉合,含地形修正/優先級/同分規則) | `ScoreNativeAI14237`(`native_ai_14237.go`) | ✓ 一致 |
| 17 | AI 法術評分 | doc11 | ✓ `0x1598A`(先前輪次已閉合) | `ScoreNativeAI1598A` | ✓ 一致 |
| 18 | AI 道具評分 | doc11 | ✓ `0x1567E`(先前輪次已閉合) | `ScoreNativeAI1567E` | ✓ 一致 |
| 19 | AI 三管線勝出者判定 | doc11 | ✓ `0x14EF0`(先前輪次) | `SelectNativeAIThreeScoreWinner` | ✓ 一致 |
| 20 | AI 移動 fallback(mode 0/1/2/3/4/5/7/8/9/10) | doc11 | ✓ 多輪已閉合,覆蓋 33 張地圖約 58% AI 單位 | `ApplyNativeAIMovementFallback` 系列 | ✓ 一致(mode 6 未見記載,可能不存在或未覆蓋,待查證) |

### 仍缺清單(誠實列出,不誇大完成度)

1. **武器命中後特殊效果(表第 5 項)**:`cVar4` type2/type3/type4 分支本輪只反組譯到「做什麼」,沒有解出「哪些武器觸發哪個 type」(`FUN_0004e8bc()` 的來源表未展開)、type3 旗標的下游消費者、type2 附加的 `+0x25` 狀態值 2~5 分別對應哪個狀態名稱。remake 完全未實作此機制。
2. **法術/道具命中率逐 ID 核對(表第 8 項)**:`0x1c7ed` 的 `record[+2]` 實際數值未逐一 dump 出來跟 `spell.json` 的 hit 欄比對,無法確認 magic.go 的「hit=0 視為必中」特例在原生端是否真的等價於 `record[+2]=100` 或另一條旁路。
3. **經驗值公式的攻方/守方等級因子細節(表第 13、14 項)**:`0x2f7b6` 的攻擊經驗公式只見「÷攻方等級」一次,`0x1c916` 的恢復經驗公式完全看不到「÷施法者等級」,兩者都跟攻略 doc02 §4.5 的文字公式有出入,需要再一輪反組譯 `0x1e292` 之外是否還有其他把 `[0x53ec8]` 除以施法者/攻方等級的呼叫點(本輪只確認了 `0x1e292` 是「消費並升級」,沒有額外除法)。
4. **傳送術/行動術/魔刃魔鎧風行/麻痺毒擊/解毒祛麻的經驗值公式**(doc02 §4.5 其餘列):本輪只反組譯了攻擊與 HP 恢復兩項,其餘六種經驗公式尚未定位對應的 `[0x53ec8]` 寫入點,**完全未反組譯**。
5. **職業等級上限特例('c'=99/'('=40 等 byte 常數)的完整列表**:`0x1e292` 只看到兩種特例分支(`cVar1(actor+7)==0x1e/0x1f→99` 上限、否則 `40` 上限),未展開 `cVar1` 完整對應哪些職業/角色,也未確認是否還有第三種特例。
6. **AI mode 6 移動 fallback**:未見於任何已閉合文件,不確定原版是否存在此 mode 或本專案尚未覆蓋。

### 對 worklist 第 245/266 行的完成度結論

- **第 245 行「反組譯戰鬥/命中/傷害/AI 演算法,與攻略公式交叉驗證」**:物理攻擊(基礎傷害/地形/暴擊/命中)、劍技、法術/道具傷害與命中、恢復(HP/MP)、輔助/狀態法術、AI 物理/法術/道具評分與勝出判定、AI 移動 fallback 共 12 個子項已有反組譯位址佐證且與攻略公式/remake 三方一致(表第 1-4、6-12、16-20 項)。**本輪新增**經驗值累加/升級機制的完整反組譯閉環(表第 15 項),以及物理攻擊暴擊分支從 data-level 補到 code-level 證據(表第 3 項)。**尚未收口**:武器命中後特殊效果(表第 5 項,原生獨有、remake 未實作)、經驗值公式的攻方/守方等級因子細節與其餘六種經驗公式(表第 13、14 項及仍缺清單第 3、4 項)。整體可視為**大部分收口,經驗值子系統與武器特殊效果為明確剩餘缺口**。
- **第 266 行「反組譯完整性盤點」**:本節(§5)即為該盤點的產出,20 個子項的三方狀態表 + 6 條仍缺清單已完整列出,可作為後續輪次的優先順序依據(建議順序:仍缺清單第 3、4 項經驗值細節 > 第 1 項武器特殊效果 > 第 2、5、6 項)。
