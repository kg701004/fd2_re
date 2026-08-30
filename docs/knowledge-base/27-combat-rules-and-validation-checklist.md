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
| 8 | 法術/道具命中率(內定命中率) | §4.3 | ✓ `0x1c7ed`→`0x4e893`:`RNG%100<record[+2]`(先前輪次) | `magic.go rollsHit`(spell.json hit 欄;hit<=0 恆 Miss,id22/35 走 0x22d1b 固定 50% gate,id24/28/29/30/31 恆 bypass) | ✓ **2026-08-30(§6.6.1)已修正並關閉**——`hit<=0` 方向訂正為恆 Miss(對映 `FUN_0001c75e`),id22/35 改用反組譯證實的 `0x22d1b` 50% gate,id24/28/29/30/31(劍技/未知)改用反組譯證實的「不經過命中判定」恆 bypass;逐 ID 用 `record[+2]` 實際數值核對 spell.json 的 hit 欄已於 §6.6 完成(0/36 誤差) |
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

### 仍缺清單(誠實列出,不誇大完成度;2026-08-19 續輪已於 §5.1 收斂第 1、3(部分)、4、5 項)

1. ~~武器命中後特殊效果(表第 5 項)~~ → **本輪(§5.1)已解出來源與觸發武器全列表**,只剩 type3 旗標下游消費者未追、type2/4 狀態/加成的玩家可見名稱未知。
2. **法術/道具命中率逐 ID 核對(表第 8 項)**:`0x1c7ed` 的 `record[+2]` 實際數值未逐一 dump 出來跟 `spell.json` 的 hit 欄比對,無法確認 magic.go 的「hit=0 視為必中」特例在原生端是否真的等價於 `record[+2]=100` 或另一條旁路。**本輪未展開**(時間優先給了武器特殊效果與六種經驗公式)。
3. **經驗值公式的攻方/守方等級因子細節(表第 13、14 項)**:`0x2f7b6` 的攻擊經驗公式只見「÷攻方等級」一次,`0x1c916` 的恢復經驗公式完全看不到「÷施法者等級」,兩者都跟攻略 doc02 §4.5 的文字公式有出入。**本輪(§5.1)找到第二個獨立實作(`0x1ecc7`)呈現完全相同的「單一守方等級因子」形狀**,提高了「攻略文字重複描述、程式碼並無漏項」這個假設的可信度,但仍未 100% 排除還有其他呼叫點對 `[0x53ec8]` 做額外除法,**保留為部分開放**。
4. ~~傳送術/行動術/魔刃魔鎧風行/麻痺毒擊/解毒祛麻的經驗值公式~~ → **本輪(§5.1)六個寫入點全部找到並反組譯,完整閉合**。
5. ~~職業等級上限特例的完整列表~~ → **本輪(§5.1)確認 `0x1e292` 該分支只比對 `record+7`(portrait,非職業 class)是否為 `0x1e/0x1f`(蓋亞/渥德),函式內沒有第三分支**,「未展開」的疑慮已解除(封閉列舉,不是清單不完整);唯獨這兩人為何享有較高上限仍是設計語意、不是反組譯缺口。
6. **AI mode 6 移動 fallback**:未見於任何已閉合文件,不確定原版是否存在此 mode 或本專案尚未覆蓋。**本輪未展開**。

### 5.1 本輪延伸反組譯(2026-08-19 續輪,回應 worklist 稽核索引 L245——純靜態 Ghidra headless,唯讀 `FD2Analysis3`)

> 方法:對 `DAT_00053ec8`(已證實的持久化經驗值累加暫存)重新列出**全部** xref(前一輪的 `Probe91Worklist245b.java` 有寫但沒有把輸出存檔,本輪用等價腳本 `ProbeAudit0820.java` 重跑並把完整輸出存成 `FD2_ghidra_projects/probe_audit0820_out.txt`),對每個 caller function 做完整 `DecompInterface` 反編譯,再用 `ProbeAudit0820b.java` 對關鍵呼叫點做逐指令原始反組譯(`getInstructionAt`/`disassemble` fallback)以還原被 `-noanalysis` 模式省略掉的呼叫參數。

**A. 六種「其餘經驗公式」全部找到(關閉仍缺清單第 4 項)**——除已知的攻擊(`0x2f7b6`)與 HP 恢復(`0x1c916`)外,`DAT_00053ec8` 還有 6 個獨立寫入點,全部共用同一個「目標等級因子」:`levelFactor = target.+0x21(等級)`,若 `target.+0x20(class)` 落在 `(8,0x19)`(即 9–24)區間則 `+0x1e(30)`——與表第 13 項已證實的攻擊公式等級加成條件完全一致:

| 法術/效果 | 位址 | 公式 | 備註 |
|---|---|---|---|
| 魔刃(AP+15%) | `0x22721` | `DAT_00053ec8 += levelFactor*2` | 對每個成功目標各加一次(迴圈內) |
| 魔鎧(DP+15%) | `0x22866` | `+= levelFactor*2` | 同上,結構與 `0x22721` 幾乎逐行相同(僅欄位從 `+0x48/+0x22` 換成 `+0x4a/+0x23`) |
| 風行(HIT+15/EV+15) | `0x22997` | `+= levelFactor*2` | 同上結構,欄位 `+0x4c/+0x4e/+0x24` |
| 狀態清除(對應 item type6/7 的同一 callee) | `0x22af6` | `+= levelFactor*4` | 只在目標原本帶 marker(`record+a5!=0`)且清除成功時累加 |
| 狀態施加(對應 item type14/22) | `0x22d1b` | `+= levelFactor*8` | 有 50% 額外 RNG gate(`FUN_0004ebe3()%100<0x32`)才會執行到這行,且排除 `class==0x19/0x1a` |
| 相對定位術/瞬間移動(item type23,已知 `NativeRelocationDestinationAllowed`) | `0x2218a` | `+= levelFactor*10` | 唯一不带迴圈的版本,只對單一 `param_3` 指定 target 計一次 |

**額外確認**:MP 恢復(`0x1c9dd`)**完全沒有出現在 `DAT_00053ec8` 的 xref 清單裡**——即 native 端 MP 恢復不給經驗值,這點先前 doc27 §5 表第 10 項只標「攻略未單列」、未明確這個「零經驗」事實,本輪补上。

**B. 武器命中後特殊效果:完整解出來源鏈與全部 15 個觸發武器 id(關閉仍缺清單第 1 項的主要部分)**

`FUN_0004e8bc(itemId)` 反組譯結果只有一行:`return &DAT_000602ad + itemId*0x17;`——與已知的 item pointer helper `0x4e56c`(table base `0x602ad`、stride `0x17`)是**同一張表的第二個編譯副本**,不是獨立的「武器效果表」。原始反組譯(`ProbeAudit0820b.java` 對 `0x2f7b6` 逐指令追蹤)證實呼叫鏈是:

```
0x2f870  CALL 0x1b83d(unit, 0)     ; 找 unit 已裝備、id<0x80(武器)的 slot(已知 predicate)
0x2f87d  CALL 0x1b722(slot, unit)  ; slot -> item id(經 0x4e56c,已知)
0x2f886  CALL 0x4e8bc(itemId)      ; item id -> row 指標(與 0x4e56c 同表同 stride)
        row+9  = cVar4(type)
        row+10 = uVar9(強度值,type2/4 才用)
```

**驗證細節**:兩次 `PUSH dword ptr [ESP+0x54]` 在呼叫前後的堆疊位移完全抵銷,確認讀的是**同一個 stack slot**;比對函式序言處同一 slot 的另一次讀取(`0x2f813`,用來算 `iVar12`=傷害公式裡的 `DP`/守方角色),可確定這是 `FUN_0002f7b6` 的**第二個參數**(在本函式內扮演 `DP`/守方角色的那個 unit),而不是直覺會猜的「攻方武器」。這是**本輪的一個誠實修正**:不能假設是攻方武器觸發,只能說是「此次呼叫中扮演本函式 `param_2` 角色的 unit 之裝備武器」——若日後证实 caller 會用相反參數順序模擬反擊,這個歸屬需要重新核對,本輪未展開 caller 側的參數傳遞。

用已存在的 `docs/data/exe_tables/native_item_effect_rows.json`(215 筆 raw row,無需新反組譯,直接讀 byte[9]/byte[10])做全表分類:

| type | 筆數 | 語意(已由 `0x2f7b6`/`0x1ecc7` 反組譯確認) | id 清單(強度值) |
|---|---|---|---|
| 0 | 200 | 無特殊效果 | (其餘全部) |
| 2 | 6 | 命中後 `RNG%100<強度值` 才觸發:目標 `record+0x25` 寫入 `(RNG%4)+2`(2~5 其中一值,疑似異常狀態變體) | 4(10) 14(30) 46(10) 59(30) 65(20) 66(20) |
| 3 | 1 | 只設輸出旗標 `param_3[4]=1`,不改任何 record 欄位;下游消費者未追 | 71(強度值未使用) |
| 4 | 8 | 固定加成暴擊率:`local_2c(crit%) += 強度值` | 7(30) 11(30) 18(5) 30(20) 39(10) 43(80) 49(10) 69(20) |

**交叉連結(本輪新發現)**:type2 寫入的 `record+0x25` 標記,與 doc32 §4 已文件化的「item type6/7 → `0x22af6`,分別讀 target `+0x25/+0x26`」是**同一個 byte**——也就是說,這 6 把武器(id 4/14/46/59/65/66)命中後可能附加的異常狀態,能被特定道具(item type6)治癒。狀態的玩家可見名稱仍未知,但「哪把武器造成、哪個道具治療」這條資料流現在是封閉的。

**C. 第二個獨立的攻擊/經驗公式實作 `0x1ecc7`(先前完全未反組譯的函式)**

xref 掃描額外發現 `0x1ecc7`(body `0x1ecc7..0x1f049`)也會寫 `DAT_00053ec8`,反組譯後其結構與 `0x2f7b6` 幾乎逐行相同(同樣的地形 AP/DP% 修正、同樣的職業暴擊表 `DAT_000524a7`、同樣的 `cVar4` type2/type4 dispatch、同樣「`守方等級×ExpPerLevel/攻方等級`,若命中後 HP 未歸零再 `×傷害/守方總HP`」的經驗公式形狀),只有 `ExpPerLevel` row 的取得方式換成 `FUN_0004e84f()`(而非 `0x2f7b6` 用的 `FUN_0004e84f` 同名呼叫——**兩者其實呼叫的是同一個 helper**,只是索引輸入不同,本輪未展開兩者確切差異)。這第二份獨立編譯的實作**只看到一次守方等級相乘**,與 `0x2f7b6` 一致,強化了(但未 100% 證實)仍缺清單第 3 項「攻略文字重複描述、非漏列一個因子」的推測。`0x1ecc7` 目前只知道會寫入同一個經驗暫存,尚未追出它是被哪個更高層呼叫者使用(不同戰鬥情境?反擊?AI 專用路徑?),留待下一輪。

**D. 職業等級上限完整枚舉(關閉仍缺清單第 5 項)**:`0x1e292` 內唯一的分支是
`cVar1 = *(char*)(recordBase+7)`(portrait byte,不是 class);`if (cVar1==0x1e || cVar1==0x1f) 比對上限=='c'(99); else 比對上限=='('(40)`。
函式裡沒有第三個分支、沒有查表——0x1e/0x1f 正是 doc49 已定案的 portrait 30(蓋亞)/31(渥德),其餘所有 portrait(含全部 0–29、31 以上)一律用 40 上限。「未展開 cVar1 完整對應」的舊保留字句可以撤下:不是清單沒展開完,是**這個函式本來就只有兩種分支**,可能是遊戲刻意讓蓋亞/渥德(兩名機兵/重裝系角色)有更高等級上限;原因屬設計語意,不是反組譯缺口。

**E. doc32 L1118(worklist 稽核索引)「`0x14344` 仍待對位」已釐清**:`getFunctionContaining(0x14344)` 回傳的就是已完整記錄的 `FUN_00014237`(AI 攻擊目標評分,body `0x14237..0x145cc`)——`0x14344` 只是該函式中段的一個位址,**不是獨立的第二個 caller**。doc32 §4.1「仍待對位 `0x14344` caller」這句話描述的懸念到此可以撤下:沒有新的 caller 需要追,既有對 `0x14237` 讀 item row `+0x0b/+0x0c` 後呼叫 `0x14818` 的 caller-specific、fail-closed 描述維持不變,不需要也不應該把 `0x14344` 當成另一個獨立證據點。詳見 doc32 §4.1 的同步更新。

### 對 worklist 第 245/266 行的完成度結論

- **第 245 行「反組譯戰鬥/命中/傷害/AI 演算法,與攻略公式交叉驗證」**:物理攻擊(基礎傷害/地形/暴擊/命中)、劍技、法術/道具傷害與命中、恢復(HP/MP)、輔助/狀態法術、AI 物理/法術/道具評分與勝出判定、AI 移動 fallback 共 12 個子項已有反組譯位址佐證且與攻略公式/remake 三方一致(表第 1-4、6-12、16-20 項)。**先前一輪新增**經驗值累加/升級機制的完整反組譯閉環(表第 15 項)與暴擊分支 code-level 證據(表第 3 項)。**本輪(§5.1)新增**:六種傳送/魔刃類經驗公式全部找到並反組譯(仍缺清單第 4 項→完全閉合)、武器命中特殊效果的來源鏈與全部 15 個觸發武器 id 解出(仍缺清單第 1 項→僅剩 type3 下游消費者與狀態顯示名稱未知)、職業等級上限枚舉封閉(仍缺清單第 5 項→完全閉合)、第二個獨立攻擊公式實作 `0x1ecc7` 佐證仍缺清單第 3 項的既有假設(仍為部分開放,未完全排除歧義)。**尚未收口**:法術/道具命中率逐 ID 核對(表第 8 項)、AI mode 6(仍缺清單第 6 項)、經驗公式攻守等級因子的最後一絲歧義(仍缺清單第 3 項)。整體可視為**worklist L245 列出的四項剩餘工作(經驗值攻守等級因子、`0x2f7b6` cVar4 分支、六種經驗公式、法術命中率逐 ID)中三項已實質收口(cVar4 分支、六種經驗公式完全解決;等級因子部分收斂),只剩法術命中率逐 ID 核對與等級因子的最後驗證未動**。
- **第 266 行「反組譯完整性盤點」**:本節(§5)即為該盤點的產出,20 個子項的三方狀態表 + 6 條仍缺清單已完整列出,§5.1 是 2026-08-19 續輪的延伸成果。後續優先順序:法術/道具命中率逐 ID 核對(仍缺清單第 2 項)> `0x1ecc7` 的呼叫者定位(仍缺清單第 3 項殘留)> AI mode 6(第 6 項)> type3 旗標下游消費者(第 1 項殘留)。

**worklist 稽核索引 L245 完成度**:高。cVar4 分支、六種經驗公式、等級上限枚舉三項全部由本輪位址級證據閉合;法術命中率逐 ID 核對本輪未動,仍是唯一真正「完全未觸碰」的子項。

## 6. 法術 AoE / 命中率 / native command 大型 dispatcher 位址勘誤(2026-08-19,回應 worklist 稽核索引 L555/L557/L572)

> 方法:純靜態 Ghidra headless(`FD2Analysis3`,`-readOnly -noanalysis`,唯讀),沿 doc37 已知的 `0x1cff0`(玩家 command confirm dispatcher)往下追,對 `0x2a6bd`(doc13/37/56/91 多處引用的「native command 大型 presentation/state dispatcher」)做位址邊界檢查時發現該位址從未真正被使用——詳見 §6.3。連帶重新反組譯出真正的 dispatcher 位址 `0x2ff01`,並在其內找到 AoE 的實際套用迴圈(§6.2)。命中率部分則是把既有 `0x1c7ed→0x4e893` 結論(表第 8 項)用即時反編譯 `FUN_0001c75e`/`FUN_0001c81f` 重新逐行核實(§6.1)。腳本:`ProbeMagicAoE0820.java`、`Probe2a6bd0820.java`、`Probe2a694Disasm.java`、`ProbeScan28784Calls.java`、`ProbeFuncs2ac25.java`、`ProbeSanity1cff0.java`、`ProbeNearest.java`、`ProbeDecompile1cff0.java`、`ProbeDecompile2ff01.java`(皆存於 `FD2_ghidra_projects/`,對應 `probe_*_out.txt` 原始輸出)。

### 6.1 法術/道具命中率——與物理 HIT−EV 完全獨立(deepens 表第 8 項)

即時反編譯 `FUN_0001c75e`(entry `0x1c75e`,body `0x1c75e..0x1c81e`,即表第 8 項引用的 `0x1c7ed` 所在函式)确认:

```c
bVar8 = *(byte*)(param_1*0x50+0x20+DAT_00053a45);      // 施法者 class id
psVar2 = FUN_0004e866();                                 // spell/item record row
sVar1  = *psVar2;                                         // record+0 威力
iVar5  = aiStack_84[bVar8];                                // 依 class 索引的抗性表(word_51f96 複本,見表第7項)
local_10 = *(byte*)(psVar2+1);                             // record+2 命中率(0..100)
if (9<param_2 && param_2<0xd) { ... FUN_0001f183 地形 gate ... }  // 僅 command 10/12 額外地形檢定
iVar3 = FUN_0004ebe3();                                    // RNG
if ((int)local_10 <= iVar3 % 100) return 0;                // miss:record[+2] <= roll(0..99)
// hit:繼續呼叫 FUN_0001c81f((sVar1*iVar5)/10) 寫傷害
```

`FUN_0004ebe3` 是 doc56 已定案的 `0x4e893` RNG 核心的呼叫外殼(逐行比對過的 wrapper,非同名巧合)。這條命中判定**完全不讀** `0x2f7b6` 的 HIT/EV 欄位、不做 `(uint)HIT-(uint)EV` 減法,只用 `record[+2]` 與獨立 RNG 相比——**明確回答任務問題 2:法術/道具命中率不與物理攻擊共用 `0x2f7b6` 的 HIT−EV 公式,是完全獨立的 `rng%100<record[+2]` 機制**。命中後呼叫的 `FUN_0001c81f` 也逐行核對過表第 7 項既有結論(`(param_2*9)/10 + FUN_0004ebe3` 抖動,clamp 0,`+0x40` 直接扣寫)。**逐 ID 用 `record[+2]` 實際數值核對 `spell.json` hit 欄仍未做**(仍缺清單第 2 項維持開放,本節只補強 code-level 證據,不改變完成度)。

### 6.2 AoE 目標迴圈——確認位置,上游目標產生器仍未追完

`0x1cff0`(`FUN_0001cff0`,body `0x1cff0..0x1d4ca`,位址存在且與既有文件一致)對 command id `local_20[DAT_00053c57]` 分兩路:id∈{9..0x17,0x19,0x1a,0x1b}(即 9–23、25–27)經 `DAT_00051d01+id*4` 跳表個別處理;id∈{0..8, 0x18(24), ≥0x1c(28..31)} 直接呼叫 `FUN_0002ff01`(真正的大型 dispatcher,見 §6.3)。

`FUN_0002ff01(actorIdx, commandId, targetCount, targetArrayPtr)` 內部再依 `commandId` 分三路:
- `commandId==0x18 || commandId>0x1b` → `FUN_0002cf30`(id 24/28–31,即已閉合的 derived-strike 公式,表第 6 項 `0x276ec` 所在的族系——結構上不含多目標迴圈,單體高倍率打擊)。
- `commandId>=0x20` → `FUN_0002d80d`(未展開,超出本輪範圍)。
- 其餘(即實際只會是 `commandId∈[0,8]`,因為 9–23 已被上一層跳表分流)→ **AoE 套用迴圈**:

```c
for (iStack_34 = 0; iStack_34 < param_3 /*targetCount*/; iStack_34++) {
    iVar4 = DAT_00053a45 + (uint)*(byte*)(param_4 + iStack_34) * 0x50;  // targetArray[i] -> unit record
    iStack_38 = *(short*)(iVar4+0x40);          // HP before
    local_44  = iVar4;
    iVar3 = FUN_0001c75e();                      // 命中擲骰 + 傷害寫入(§6.1),對「這一個」target 執行
    bStack_14 = (iVar3==0);                       // 記錄這個 target 是否 miss
    iStack_50 = *(short*)(iVar4+0x40);           // HP after(真實值已寫入)
    *(short*)(iVar4+0x40) = (short)iStack_38;     // 暫時還原,供下面逐 frame 動畫用
    ...逐 frame 迴圈把 HP 從 iStack_38 動畫式地過渡到 iStack_50(數字捲動/HP bar 演出)...
}
```

即 `param_3`=目標數、`param_4`=目標 unit-index 陣列(byte array),對陣列中**每一個**目標各自獨立呼叫一次 `FUN_0001c75e`(各自擲一次命中骰、各自吃傷害公式),迴圈本身對 id 0–8 一視同仁,不分辨形狀。**這就是「AoE(range>0)打幾個目標」的原生套用機制**:range 造成的多目標效果,是由「呼叫 `0x1cff0`/`0x2ff01` 之前,誰把 N 個合法目標填進 `param_4` 陣列」決定,dispatcher 本身只是機械地對陣列每格重跑一次命中+傷害。**尚未追完的缺口**:`FUN_0001cff0` 呼叫 `FUN_0002ff01` 的實際傳參處(本輪因先反編譯 caller、後才建立 callee 型別,decompiler 未重新解析呼叫點,只顯示 `FUN_0002ff01();` 不含實參)還沒有回頭用逐指令反組譯把 `param_3/param_4` 的**產生來源**釘死;`0x1cff0` 內已知會在跳到 id-based 分支前呼叫 `FUN_00014818()`/`FUN_000115b6()`(一般情形)或 `FUN_000149f8()`(僅 `local_20[..]==0x1e` 即 id30 專用)取得候選/確認清單,這些函式的輸出是否直接餵給 `param_3/param_4`、range 半徑/形狀在哪一步被套用,~~仍是開放問題~~——**2026-08-20 續輪(§6.4)已用逐指令反組譯完整追完,見下**。

**一個相關但不可混用的旁支發現**:另在 `FUN_00014ef0`(0x14ef0)/`FUN_00015055`(0x15055)一叢(由 `FUN_00013a9f` 依 `unit[+0x34]&0xf` 狀態機呼叫,即 doc11 的敵方 AI 行動執行,非玩家)裡也看到 `cmd>=0x10 → spellId=cmd-0x10 [0x150d3]` 後呼叫 `FUN_000149f8` 做「以起點/終點方向逐格步進、收集符合陣營 selector 的 unit」;但傳入的步進次數(count 參數)在此路徑上等於 **spellId 本身**(`0x150d6: PUSH EAX` 緊接 `0x150d3: SUB EAX,0x10` 的結果),不是任何距離/半徑欄位——若 spellId=0 該迴圈完全不執行、收不到任何目標,這個結果本身很可疑,尚未排除是筆者參數對應錯誤或該路徑本就只服務極少數 AI 分支。**這是 AI 執行路徑,不是玩家 command ring 的 `0x1cff0/0x2ff01` 路徑**,不能拿來回答玩家施法 UI 的 AoE 問題,僅記錄以免下一輪重複走冤枉路。同時**修正 doc37 §0 的舊標籤**:doc37 把這叢函式稱為「選單施法」(暗示玩家選單直接施法路徑),但 `FUN_00013a9f` 的呼叫閘門(`unit[+0x34]&0xf` 狀態值)是 doc11 已定案的敵方 AI 行為狀態欄,此路徑應正名為「AI 法術執行」,不是玩家路徑。doc37 §0 另引用「`0x015195`(push ebp; call 0x28784)」作為施法演出呼叫點,本輪即時反組譯該位址實際指令是 `CALL 0x2dfc8`,並對整個可執行段做位元組樣式掃描(`E8`+rel32)找 `0x28784` 的直接呼叫者,**掃描結果為零筆**——doc37 這個特定位址引用需要重新核實(可能是間接呼叫、也可能是舊分析狀態下的誤記),本輪未展開,留待下一輪用逐指令反組譯或間接呼叫掃描補上。

**2026-08-24 live 交叉驗證補充(doc58 續六十二)**:上面 `+0x40`(HP)、以及 `+0x44/+0x46`(MP)、
`+0x48/+0x4A/+0x4C/+0x4E`(AP/DP/HIT/EV)這組 `0x50`-byte unit record 欄位配置,對**敵方 record
(含 boss 級單位)完全適用,不需要另外的敵方專屬 offset**——ch27 戰場對 slot16(雜兵,HP15/15/
MP15/15/AP465/DP195/HIT95/EV15)與 slot24-26(機甲隊長,class`0x74`,HP32/32/MP32/32/AP232/
DP212/HIT182/EV32)逐 record 用 debugger `D` 指令核對過,欄位語意與上述 ally 表格逐 byte 吻合。
doc58 續五十九~六十一曾記錄「敵方 record 的 `+0x40` 是 LV 不是 HP」,經本輪核對是誤判——真正
原因是這 3 隻隊長的 maxHP 設計值恰好等於 32,與其 LV 32 數字重合造成混淆,record 本身結構完全
共用同一份 ally/enemy 通用欄位表,見 doc58 續六十二 §2。

### 6.3 位址勘誤:「`0x2a6bd`」不是有效的指令邊界

`0x2a6bd` 被 doc13/doc37/doc56/doc91 多處引用為「native command 大型 presentation/state dispatcher」入口。本輪對它做直接邊界檢查(`getInstructionAt`/`getInstructionContaining`):

- `getFunctionContaining(0x2a6bd)` 回傳 `FUN_0002a694`(body `0x2a694..0x2a856`,僅 451 bytes),反編譯後是一個 ≤3 次迴圈的調色盤/貼圖特效函式(呼叫 `FUN_0004e29c`/`FUN_00015f84`/`FUN_0004e7dd`),與「大型 presentation dispatcher」的既有描述完全不符。
- `getInstructionAt(0x2a6bd)` 回傳 `null`;`getInstructionContaining(0x2a6bd)` 回傳 `0002a6bb  MOV EAX,dword ptr [ESP+0x24]`(4 bytes:`8B 44 24 24`)——`0x2a6bd` 剛好落在這條指令中間(第 3 個 byte)。**`0x2a6bd` 在目前的 `FD2Analysis3`(新版參考 EXE)裡根本不是指令開頭,只是別條指令中間的一個位元組**。
- 同一方法檢查 doc37 引用的另一個相關位址 `0x276ec`(「id==0x18 走特別分支 0x276ec」):同樣落在 `0002276e9 CMP EAX,dword ptr [0x53c57]` 這條 6-byte 指令中間(第 4 個 byte),也不是有效指令邊界。
- 對照組:`0x1cff0`、`0x1d6c8`、`0x27fc9` 三個同批引用位址,`getInstructionAt` 全部命中(`insnStart=true`),函式邊界與既有文件描述吻合——**不是整批位址系統性平移錯誤,只有 `0x2a6bd`/`0x276ec` 這兩個孤立引用有問題**,判斷為手動反組譯階段的個別誤記(從反編譯 C 虛擬碼往回估位址時的常見誤差),不是本專案位址系統的整體失準。

順著 `0x1cff0`(§6.2 已確認完整、正確)往下重新反組譯,找到真正符合「id∈{0..8,0x18,≥0x1c} 直接呼叫」「大型 presentation/state dispatcher」描述的函式是 **`0x2ff01`**(`FUN_0002ff01`,body `0x2ff01..0x30e24`,3876 bytes,規模與描述相符)。**結論:doc13/37/56/91 裡的「`0x2a6bd`」引用,實際指的應是 `0x2ff01`;「id==0x18 走 `0x276ec`」的正確目標是 `0x2ff01` 內部的 `commandId==0x18 || commandId>0x1b` 分支,實際跳去的是 `0x2cf30`**。本文件僅記錄此勘誤與新位址證據,**未回頭修改 doc13/37/56 的既有引用**(超出本輪任務範圍,且那些文件的既有功能性結論——如表第 6 項 derived-strike 公式——本身仍是對的,只有位址標籤需要在未來一輪統一置換)。

### 6.4 AoE 目標陣列上游生成器——完整追出(2026-08-20,回應 §6.2 殘留缺口)

> 方法同 §6:純靜態 Ghidra headless(`FD2Analysis3`,`-readOnly -noanalysis`)。從 §6.2 已知的 `FUN_0002ff01` call site 往上,對 `FUN_0001cff0` 整個函式體(`0x1cff0..0x1d4ca`)做逐指令原始反組譯(而非只看 decompile 虛擬碼,因為 decompiler 在單獨反編譯 `FUN_0001cff0` 時尚未解析出 `FUN_0002ff01`/`FUN_00014818` 的簽名,呼叫點參數會被吃掉顯示成 `FUN_xxx();`),逐一核對每個 `CALL` 前的 `PUSH` 序列釘死實際傳參。腳本:`ProbeAoESource0820.java`(對應 `probe_aoe_source_0820_out.txt`)、`ProbeAoEGenerators0820.java`(`probe_aoe_generators_0820_out.txt`)、`ProbeAoE14818Disasm0820.java`(`probe_aoe_14818_disasm_0820_out.txt`)、`ProbeAoERangeMap0820.java`(`probe_aoe_rangemap_0820_out.txt`)、`ProbeAoEStamper0820.java`(`probe_aoe_stamper_0820_out.txt`),皆存於 `FD2_ghidra_projects/`。

**結論先講:上游生成器找到了,是 `FUN_00014818`(`0x14818`),它把「施法者目前選定的座標 + 法術/道具記錄裡的一個 range/shape byte」展開成「全地圖內符合陣營篩選的目標 unit-index 陣列」,§6.2 的 `FUN_0002ff01` 只是機械地套用這份已經展開好的陣列。** 完整鏈路:

1. **`FUN_0002ff01` 的真正呼叫點**:`0x1d43c`(在 `FUN_0001cff0` 內)。逐指令核對其 4 個實參(`__stdcall`,由近到遠依序對應 `param_4..param_1`):
   ```
   0001d423  MOV EAX,ESP                              ; EAX = 目前 ESP(指向 stack 上已建好的 byte 陣列)
   0001d425  PUSH EAX                                  ; -> param_4 targetArrayPtr
   0001d426  PUSH ESI                                  ; -> param_3 targetCount
   0001d427  MOV EAX,[0x00053c57]
   0001d42c  MOVZX EAX,byte ptr [ESP+EAX*0x1+0xd0]      ; EAX = local_20[選定索引] = commandId
   0001d434  PUSH EAX                                  ; -> param_2 commandId
   0001d435  PUSH dword ptr [ESP+0xf8]                 ; -> param_1 actorIdx(FUN_0001cff0 自己的傳入參數)
   0001d43c  CALL 0x0002ff01
   ```
   即 `param_3`(目標數)= `ESI`、`param_4`(目標陣列指標)= 呼叫當下的 `ESP`,兩者都是同一個 stack frame 裡「先前已經被填好」的值——順著往回找是誰設定 `ESI`/那塊 stack 記憶體。

2. **`ESI`/陣列的產生者是 `FUN_00014818`**,在 `FUN_0001cff0` 內對一般情形(非 `commandId==0x17` 特例)實際呼叫兩次,分別用 spell/item 記錄的**兩個不同 byte 欄位**當 range 參數:
   - 第一次(`0x1d2bf`):`param_4 = record[+3]`(來自 `FUN_0004e866` 回傳的 record row,即 §6.1 命中率公式所用的同一筆記錄),`param_6 = record[+6]`(陣營/side 選擇器),`param_1/param_2 = DAT_00053ab1/DAT_00053ab5`(目前游標/施法座標)。回傳的候選數與陣列接著餵給 `FUN_000115b6`(`0x1d2e3`)——**這個函式不是生成器,是互動確認迴圈**:內部 `FUN_00012dac()` 讀輸入事件,對 `0x2c/0x4c`(確認鍵)、`0x48/0x50/0x4b/0x4d`(方向鍵→呼叫游標移動 `FUN_00011b48/b9b/c59/bfa`)分派,即「玩家在 `record[+3]` 這個『可選取範圍』內用游標挑目標/確認位置」的 UI 迴圈。
   - 第二次(`0x1d32a`,confirm 完成後):`param_4 = record[+4]`(**另一個** byte 欄位,不是 record[+3]),其餘參數結構相同。這次呼叫的回傳值(`EAX`)才是最終寫進 `ESI` 並流向 `0x1d43c` 的 `targetCount`。**特例**:若 `commandId==0x1e`(30),改用 `FUN_000149f8`(`0x1d35c`,直線步進生成器,`steps = record[+3]-0x10`,與 §6.2 附記的 AI 路徑 `0x150d3` 用法同構)取代第二次 `FUN_00014818`。
   - 因此 `record[+3]`=「選取階段(游標可達)範圍」、`record[+4]`=「實際生效(AoE 展開)範圍」是兩個獨立欄位,呼叫同一個生成器函式,語意類似「先選點、再以另一個半徑在該點展開」。

3. **`FUN_00014818(originX, originY, outBuf, rangeByte, extraThreshold, sideSelector)`**(body `0x14818..0x149f7`,480 bytes)原始反組譯逐行核實,結構分三段:
   - `rangeByte < 0x10`:先無條件呼叫 `FUN_0004e8a5(...)`(23 bytes,`&DAT_00061646 + idx*0x14` 的陣列存取殼)與 `FUN_0004e390(...)`(見下第4點,實際播種+啟動遞迴 flood fill);接著若 `extraThreshold(param_5)!=0` 才額外跑一段「掃全地圖、用 `FUN_00037932`(`0x37932`,純 `abs()`)算 `|col-originX|+|row-originY|` 曼哈頓距離、`< extraThreshold` 就標記地圖緩衝區(`DAT_00053a51+7`,每格 4 bytes)為 `0xff`」的迴圈——**這段在兩次 `0x14818` 呼叫裡 `extraThreshold` 都固定傳 `0`,永遠不執行**,證實實際 AoE 半徑機制不是這段,而是下面第4點的遞迴 flood fill。
   - `rangeByte >= 0x10`:改成兩個獨立的列/欄掃描,用 `rangeByte-0x10` 當門檻(直線/十字類形狀,與 `FUN_000149f8` 的 `steps=record[3]-0x10` 編碼同一套「≥0x10 表示直線形」慣例)。
   - 不論走哪一段,最後統一跑 `0x14940..0x149f0`:掃描全部 `DAT_00053beb` 個 unit,篩「存活(`unit[+5]&1==0`)且所在格在地圖緩衝區裡 `!=0xff`」且「`unit[+6]` 陣營欄位符合 `sideSelector`(0=己方 `==0`,1=非己方 `!=0`,2=`==1`,3=`==2`)」者,把 roster index 寫進 `outBuf` 並計數,回傳計數——**這就是把「地圖上哪些格子在範圍內」轉成「哪些 unit-index 該挨這次法術/道具」的最後一步,亦即 `FUN_0002ff01` 的 `param_3/param_4` 的直接來源**。

4. **半徑真正怎麼「長出來」**:`FUN_0004e390`(`0x4e390..0x4e42b`,156 bytes)把起始格座標與一個初始「預算」寫進共用地圖緩衝區(`param_8[(width*originRow+originCol)*4+7] = value`),然後呼叫 `FUN_0004e42c`(`0x4e42c..0x4e4bd`,146 bytes)——逐指令核對後確認這是一個**標準四方向遞迴 flood fill**:對右/左/下/上 4 個鄰格,各自呼叫 `FUN_0004e4be`(留在 register 呼叫、本輪未反編譯的葉節點函式,依 `JC`/進位旗標判斷「已訪問/越界/預算用盡」)嘗試標記,若未被擋(`!JC`)且預算(`EBX`,每走一步消耗一個單位)仍夠,就遞迴呼叫自己继续往外擴散——即「以起點為中心、以 `rangeByte` 換算出的預算為半徑,BFS 式往外塗滿地圖緩衝區」,這正是把 `record[+3]`/`record[+4]` 這個純量 range byte 轉成「哪些地圖格子算在範圍內」的實際機制。

**結論**:AoE(range>0)目標清單生成的完整鏈路——`spell/item record[+3]`(選取範圍)/`record[+4]`(生效範圍)→ `FUN_00014818` 依 `<0x10`/`>=0x10` 分流成「`FUN_0004e390`+`FUN_0004e42c` 遞迴 flood fill 塗地圖緩衝區」或「列/欄門檻掃描」→ 掃描全部 unit、按緩衝區命中 + `record[+6]` 陣營篩選器收集 roster index → 回傳陣列+計數 → 經 `FUN_0001cff0` 的 stack frame 原樣傳給 `FUN_0002ff01` 的 `param_3/param_4` → §6.2 已證實的逐目標套用迴圈——**已用位址級反組譯完整釘死,不再是開放問題**。唯一未展開的末梢是葉節點 `FUN_0004e4be` 本身(地圖緩衝區的實際寫入/邊界判斷原語)與 `FUN_0004e8a5` 回傳陣列的確切用途,兩者都只影響「精確步進代價/資料表內容」的細節,不影響本節已確立的「range byte → flood fill → 陣營篩選 → unit-index 陣列」整體機制結論,留待需要精確重現地圖形狀時再補。

### 6.5 `0x2cf30`/`0x2d80d` 完整反組譯——derived-strike 演出/SFX 迴圈 + 四類複合 handler 逐支釘死(2026-08-24)

> 背景:worklist 91 第 792 行標記 `0x2ff01` 分支結構「id 24/28–31 走 `0x2cf30`、id≥32 走 `0x2d80d`」首次有反組譯佐證,但兩個 callee 本身尚未逐指令展開。方法:純靜態 `tools/ghidra_batch_probe.py`(`disasm`/`decompile`/`xref_to`/`call_scan`/`bytes` 五種 action,`FD2Analysis3`,`-readOnly -noanalysis`)。`call_scan` 對兩個位址各自窮舉全 EXE,確認**唯一 caller**都在 `FUN_0002ff01` 內(`0x2cf30`←`0x3003f`、`0x2d80d`←`0x30012`),與既有分支結論一致,無第二呼叫路徑。

**`0x2cf30`(`FUN_0002cf30`,body `0x2cf30..0x2d80c`,2269 bytes,ID24/28/29/30/31 derived-strike)**——逐指令反組譯+decompile 確認:

- **倍率表訂正**:`if id==0x18(24) mult=15; elif id==0x1c(28) mult=20; elif id==0x1d(29) mult=12; else mult=18`。**`else` 分支同時覆蓋 `id==0x1e`(30,音速刃)與 `id==0x1f`(31,`command_labels.json` 該 slot label 為空字串)**——先前記錄「倍率 15/20/12/18 分別對應 24/28/29/31」的措辭會讓人誤以為 30 沒有倍率或另有分支,實際上 30/31 共用同一個「非 24/28/29」的預設值 18,已在 `verified_addresses.json` 訂正措辭。傷害本體 `trunc(actor.+0x48(AP,short)*mult/10)`,經已知的 `0x1c81f` HP writer 寫入(與法術/道具傷害共用同一個底層寫入核心,只是傷害數值來源不同)。
- **derived-strike 有自己獨立的逐目標演出/SFX 迴圈,不是單純呼叫 `0x1c81f` 就結束**:對每個 target 呼叫完 `0x1c81f` 後,再走一個「hit-event 陣列回放」迴圈——陣列來源是 `FUN_000314de()`(先於主迴圈呼叫一次,回傳指標存入 `local_28`/`DAT_0005414b`),逐 event(`local_24` 從 `local_28[2]` 掃到 `*local_28`)檢查 `local_28[event+5]!=0` 才呼叫 `FUN_00025a96`(=已知 `play_sfx_a`,`0x25a96`)觸發音效,`local_28[event+4]==1` 時把這一步的 HP 顯示值分成 N 步遞減播放(`id==0x1c`(28,淒煌斬)用 8 步、其餘三招用 1 步——這是**淒煌斬相對其他三招唯一有實質差異的演出**,同時它在函式前段的資源載入區也多一次 `FUN_0002facd()` 繪製呼叫,其餘三招沒有)。event 陣列本身逐 byte 完整語意(哪個 event 對應揮擊/命中/爆擊等)未展開到 leaf level,但「呼叫 `0x1c81f` 算傷害→回放 hit-event 陣列觸發 `play_sfx_a`」這個機制結論已用位址級反組譯釘死。
- 函式前段另外無條件載入 3 個資源(`DAT_0005413f`/`DAT_00054143`/`DAT_00054147`,各一次 `FUN_000111ba()`),四招共用,未鑑定型態,不影響上述結論。

### 6.6 法術/道具命中率逐 ID 核對(2026-08-30)——關閉表第 8 項「仍缺清單」的最後一項

> 回應 §5「仍缺清單」第 2 項、§6.1 結尾「逐 ID 用 `record[+2]` 實際數值核對 `spell.json` hit 欄仍未做」的遺留缺口,以及 `91-worklist.md` 第 1159 行、`32-item-combat-stats-re.md` 第 756 行同一項的稽核索引。方法:純靜態直接讀取 `FD2.EXE` 二進位位元組(Python `seek`/`read`),不需要 DOSBox-X 或 Ghidra live session。

**基準版本確認**:對照 `docs/data/fd2-reference-files.json`,`C:\Users\kg701\Desktop\GAME\FD2\FD2.EXE`(509158 bytes)的 MD5(`33464c81e6a364fd0660141139aa8e6e`)與記載的「新版(1998 重打包版)」canonical hash 完全吻合(`FD2_USB`、`FD2_APK` 兩份備份同大小同 hash,互為印證),確認用這份檔案逐 byte 核對即可,不需要額外版本判定。

**核對結果:36 條記錄的 `hit` 欄與 `raw` dump 的實際數值 0/36 有誤,但 `spell.json` 的 `off` 欄位是舊版(357074 B,已遺失)位址,不是目前 `FD2.EXE` 的真實 file offset**——直接用 `off+2` 讀新版檔案,36 筆全部不吻合(讀到的是新版檔案裡完全無關的位元組);把每筆 `off` 加上 `03-exe-and-data-structures.md`/`tools/dump_exe_tables.py` 已定案的舊↔新版固定位移 `0x25214` 後(如 id0:`0x557fd`→`0x7aa11`),`off+2` 讀到的 byte 與 `spell.json` 的 `hit` 欄**36/36 完全一致**,`raw` 全 7-byte dump 也逐位元組吻合(用 `dmg`(u16 LE)/`dist`/`range`/`mp`/`target` 一併核對,全部相符)。換算後的位址與 `tools/dump_exe_tables.py` 目前寫死的 `ANCHORS["spell"] = (0x7AA11, ...)` 完全對上(id0 換算結果正是 `0x7aa11`),證實：

- `spell.json` 的**資料值**(`hit`/`dmg`/`dist`/`range`/`mp`/`target`/`raw`)是從正確的新版 canonical `FD2.EXE` 位址正確 dump 出來的,不存在數值誤讀。
- `spell.json` 的 **`off` 欄位字串**是這份檔案改版基準前(2026-08-14 之前)殘留的舊版位址標籤,`dump_exe_tables.py` 在 2026-08-20 已改成直接輸出新版 offset,但 `spell.json` 本身沒有跟著重新產生,所以檔案內文字上的 `off` 目前對不上現行工具會輸出的值——這是文件/產出物的標籤過期,不是萃取邏輯的錯誤,對 `hit`/`dmg` 等實際數值判讀無影響。留給下一輪:重跑 `tools/dump_exe_tables.py` 覆寫 `spell.json`(以及其他仍是舊版 `off` 標籤的表,若有)使 `off` 欄與現行工具輸出一致,純屬 housekeeping,不阻塞下面的語意結論。

**hit=0 的原生語意——重新逐行核對 `FUN_0001c75e`(即 §6.1 已貼的反編譯),確認「hit=0 → 恆 miss」成立**:

```c
local_10 = *(byte*)(psVar2+1);        // record+2 命中率(0..100)
iVar3 = FUN_0004ebe3();                // RNG
if ((int)local_10 <= iVar3 % 100) return 0;   // miss:record[+2] <= roll(0..99)
```

`iVar3 % 100` 的結果域是 `[0, 99]`(§6.1 原文已標註,C 的 `%` 對正數/該 RNG 核心 `0x4e893` 的輸出恆為非負);當 `record[+2]==0` 時,`0 <= roll` 對 `roll∈[0,99]` **恆為真**,函式因此**恆進入 `return 0`(miss)分支,不可能進入下面呼叫 `FUN_0001c81f` 寫傷害的 hit 分支**。即:**native 端 `hit=0` = 恆 miss,不是恆 hit**。20 條 dump 值為 0 的記錄(id 13–25、28–31、33–35,共 20 筆,見上表)在原生引擎裡,只要真的透過這條 `FUN_0001c75e` 路徑判定命中,結果就是每次都不會命中。

**與 `remake/internal/battle/magic.go` 比對——確認方向相反的 bug,本輪不修正**:

```go
// magic.go:120-125
func rollsHit(sp Spell, rng *rand.Rand) bool {
	if sp.Hit <= 0 {
		return true   // ← 現況:hit<=0 視為「恆中」
	}
	return rng.Intn(100) < sp.Hit
}
```

現況與原生邏輯**方向相反**:native `record[+2]==0` 恆 miss,remake `sp.Hit<=0` 恆 hit。`magic.go` 檔頭註解(1-18 行)與本函式註解(118-119 行)顯示這是**刻意的設計取捨**,不是疏忽:開發者觀察到這 20 條 hit=0 記錄裡包含攻略文字明確描述「劍技恆中(100%)」的 4 招(id24/28/29/30)與「攻擊性輔助法術命中率均 50%」的封咒/組合技類,兩者都與「hit=0 恆 miss」矛盾,因此選擇「hit=0 → 恆 hit」這條**可被資料驗證但語意仍是猜測**的折衷規則,而非採用未被 dump 值印證的「50%」猜測值。本輪的逐 ID 核對**沒有解開這個矛盾**,只是新增了一個獨立證據:至少在 `FUN_0001c75e` 這條命中判定路徑本身,`record[+2]=0` 的機器語意就是恆 miss,不支援「恆 hit」這個假設;矛盾的真正解法(這些法術/道具的命中判定是否根本不走 `FUN_0001c75e`、而是像劍技一樣有另一條獨立公式)仍待未來一輪反組譯 id24/28/29/30(劍技,已知另有 `0x2cf30` derived-strike 路徑,§6.5)與 id22/23/34/35(封咒/傳送/組合技)實際使用命令 dispatcher 的哪一條分支來釐清。

**影響範圍(供下一輪抓 bug 用,本輪不修正程式碼)**:`applySpell`(`magic.go:278-332`)只在 `sp.Target==0`(第 280 行)才呼叫 `rollsHit`。20 筆 `hit=0` 記錄裡 `target=0` 的有 id24/25/26/27/28/29/30/31/34/35 共 10 筆;其餘 10 筆(`target=1` 的治療/輔助/清除狀態,以及 `target=3` 的傳送 id23)完全不經過 `rollsHit`,不受此 bug 影響。在這 10 筆裡:
- **有實際遊戲效果、現在會被 bug 影響**:id25(行動術)、id26(毒擊)、id27(麻痺)、id34(破壞神)、id35(暗邪鬼)——`applySpell` 對這幾個 case 有真正的傷害/狀態寫入邏輯,目前因為「恆 hit」bug 而保證每次施放都生效,若日後照原生語意改成「恆 miss」,這幾招會變成永遠打不中/無效果(除非同時查清上一段提到的矛盾)。
- **目前是 no-op,bug 暫時無感**:id24/28/29/30(劍技)、id31(未知)——`applySpell` 對應 case 直接 `return CastResult{Target: tgt}` 不做任何傷害/狀態(注解「待實裝加乘率」),不論 `rollsHit` 回傳 true/false 都沒有可觀察差異,但等這些 case 真正實作傷害後,同一個方向錯誤的 bug 會立刻變成有感。

**結論**:`spell.json` 的 `hit`/`raw` 等實際資料值全部正確(0/36 誤差),`off` 欄位是需要 housekeeping 的過期標籤;`hit=0` 的原生機器語意是「恆 miss」而非「恆 hit」;`magic.go` 現行 `rollsHit` 對 `hit<=0` 的「恆 hit」處理與此相反,是一個已知、已在程式碼註解裡承認為刻意折衷、但今天的逐位元組核對確認其假設方向錯誤的 bug,標記為**未修正**,留待下一輪先解開「這些 id 是否真的走 `FUN_0001c75e`」這個前置問題後再動 `magic.go`。

#### 6.6.1 修正落地(2026-08-30 續輪)

> 承接上一節「未修正」的收尾:先重新核對「id25/26/27/34/35 受影響」這句話本身,再決定怎麼改 `magic.go`。

**先訂正上一輪的一個錯誤**:直接重新讀 `spell.json` 逐 ID 核對(不只信任上一輪的文字敘述)發現,「hit=0 且 target=0(會呼叫 `rollsHit`)」的真正集合是 **id22/24/28/29/30/31/35(7 筆)**,不是上一輪寫的「id24/25/26/27/28/29/30/31/34/35(10 筆)」——id25 與 id34 實際 `target=1`(治療/輔助類,`applySpell` 的 `sp.Target==0` 前置條件不成立,完全不呼叫 `rollsHit`,不受此 bug 影響,不論修好前後都一樣);id26/id27 實際 `hit=50`(不是 0,走的是 `rng.Intn(100)<sp.Hit` 一般擲骰分支,同樣不受這個「hit<=0 特例」的方向 bug 影響)。7 筆真集合裡,`applySpell` 目前有實際效果(受此 bug 影響)的只有 **id22(封咒術)、id35(暗邪鬼組合技)**;id24/28/29/30(劍技)、id31(未知)`applySpell` 對應 case 仍是 `return CastResult{Target: tgt}` 的 no-op,無論 `rollsHit` 回什麼都無可觀察差異。

**id22/id35 進一步查證後發現它們也不是單純的「hit<=0→miss」個案**:反組譯 `remake/internal/battle/native_item_marker_application.go`、`native_command_compound.go`、`native_raw_application.go`(既有的獨立 0x22d1b RE 產物,`docs/knowledge-base/32-item-combat-stats-re.md:442-483` 同步記錄)證實,封咒術(id22)與暗邪鬼(id35,內含封咒/毒擊/麻痺三重狀態,§6.5 已證實其 3 個子效果各自呼叫 `0x22d1b`)的原生命中判定完全**不經過** `FUN_0001c75e`/`record[+2]`,而是 `0x22d1b` 狀態施加核心內建的**編譯期常數 50% RNG gate**——`spell.json` 裡 id22 的 `hit` dump 值是 0、id26/27 是 50,這兩個數字都與 `0x22d1b` 的 50% gate 無因果關係(0x22d1b 不讀 `record[+2]`),純屬巧合式數值重合,不能拿 `hit` 欄位當這幾個 id 的命中率來源。

**實際修正**(`remake/internal/battle/magic.go` `rollsHit`,約 118-146 行):
```go
func rollsHit(sp Spell, rng *rand.Rand) bool {
	switch sp.ID {
	case 22, 35:
		return rng.Intn(100) < 50 // 0x22d1b 固定 50% gate,非 record[+2]
	case 24, 28, 29, 30, 31:
		return true // 0x2cf30 derived-strike 不呼叫命中判定,固定套用(劍技恆中)
	}
	if sp.Hit <= 0 {
		return false // FUN_0001c75e:record[+2]<=roll(0..99) 恆真 → 恆 miss
	}
	return rng.Intn(100) < sp.Hit
}
```
`combat.go` 的 `rollsHitPct` 檔頭註解同步更新(舊註解說 magic.go 是「必中特例」,現已不成立)。

**測試**:`magic_test.go` 新增 `TestRollsHit_HitZero_AlwaysMisses`(通則:不在特例清單的假想 ID,hit<=0 對 100 次擲骰恆 Miss)、`TestRollsHit_SealSpell_FiftyPercentGate`(id22 對 60 次擲骰同時出現命中與 Miss)、`TestRollsHit_SwordTechniquesAndUnknown_AlwaysBypassHitCheck`(id24/28/29/30/31 對 20×5 次擲骰恆 true);既有 `TestApplySpell_ComboSpells` 的暗邪鬼(id35)案例從「單一固定 seed 斷言命中」改成 40 次擲骰迴圈,驗證命中/Miss 皆出現且三個狀態恆同步(共用同一次擲骰,remake 既有簡化,本輪不展開)。`go build ./...`、`go test ./...` 全綠(`internal/battle` 526 個測試全過,含新增/調整的 4 個)。

**實際遊戲行為變化**:id22(封咒術)、id35(暗邪鬼)兩招在 remake 裡從「每次施放保證生效」變成「50% 機率生效」(對映原生 0x22d1b 真實機率);id24/28/29/30/31 因目前仍是 no-op,行為無變化(但已排除未來實作傷害時重蹈方向錯誤的隱患);id25/26/27/34 本來就不受此 bug 影響,行為無變化。**此項現已關閉,不再是開放問題。**

#### 6.6.2 id24/28/29/30/31 傷害實裝(2026-08-30 續輪)

> 承接 §6.6.1「applySpell 對這些 case 目前仍是待實裝的 no-op」的遺留缺口。方法:先確認證據是否已足夠,不是重新反組譯——`native_command24.go`(§6.5 的落地產物)早已把 `0x2cf30` 的傷害公式(`trunc(actor.AP*mult/10)-DP`,經 `ResolveNativeCommandDerivedStrikeDamage` 隨機化)實作成一個獨立、已測試的 helper,只是服務「native command」cursor-driven 派送路徑(`ExecuteNativeCommandDerivedStrike`/`ExecuteNativeCommand30`),從未被 `magic.go` 的 `applySpell`(spell.json/`CastArea` 施法路徑)呼叫過。兩條路徑對應同一批遊戲指令(24/28/29/30/31),證據已經是位址級反組譯釘死的(§6.5「已用位址級反組譯完整釘死,不再是開放問題」),不是猜測,因此本輪判定**有充分證據可以實作**,不需要新的動態驗證或反組譯。

**實際修正**(`remake/internal/battle/magic.go`):

- 新增 `derivedStrikeMultiplier(id int) int`:24→15、28→20、29→12,其餘(30/31)→18,對映 §6.5 訂正後的倍率表。與 `native_command24.go` 的 `nativeCommandDerivedStrikeMultiplier` 刻意分開維護(該函式服務 id30 有專屬 line-selector 入口的 native command 路徑,故意不含 30;這裡服務沒有該特例需求的 `CastArea` AoE 路徑,直接把 30 併入)。
- `applySpell` 的 `case 24, 28, 29, 30, 31` 從 `return CastResult{Target: tgt}`(no-op)改成呼叫既有、已測試的 `ResolveNativeCommandDerivedStrikeDamage(caster.AP, tgt.DP, derivedStrikeMultiplier(sp.ID), rng)`,套用傷害、回傳 `Amount`。命中沿用 §6.6.1 已修正的 `rollsHit` 恆 true bypass,不重複擲骰。目標選取沿用 `CastArea` 既有的 spell.json `Range`/`Dist` AoE 模型,不引入 native command 系統 id30 專屬的 cursor line-selector(兩套目標選取邏輯本來就分開維護,不強行合併)。
- `awardCastExp` 把 24/28/29/30/31 從「特例回 0(注解:劍技待實裝加乘率)」移除,讓它們落到既有的「一般攻擊型法術」預設分支(`AttackExp`)——這與 `native_command24.go` `ExecuteNativeCommandDerivedStrike` 已經做出的判斷一致(該檔案函式註解自陳「這是 judgment call,不是逐位元組證明」:這些指令仍是透過同一個 `0x1C81F` 底層寫入核心造成的普通傷害,理應算一般攻擊經驗)。這不是本輪新增的 RE 結論,只是讓 `applySpell` 追上 sibling 子系統已經做出的既有決定,避免同一款遊戲機制在兩個子系統裡經驗值行為不一致。

**測試**(`remake/internal/battle/magic_test.go`):新增 `TestApplySpell_DerivedStrikeDamage_MatchesNativeFormula`(對 24/28/29/30/31 逐 id 比對 `CastArea` 的傷害輸出與獨立呼叫 `ResolveNativeCommandDerivedStrikeDamage`(同一 AP/DP/倍率/RNG seed)完全一致)、`TestApplySpell_DerivedStrikeAwardsAttackExp`(Own 陣營造成傷害應取得 >0 經驗)、`TestDerivedStrikeMultiplier_MatchesDoc`(逐 id 核對倍率表);`TestRollsHit_SwordTechniquesAndUnknown_AlwaysBypassHitCheck`/檔頭註解同步移除「仍是 no-op」的過期敘述。`go build ./...`、`go test ./...` 全綠。

**仍未展開(誠實列出,非本輪範圍)**:derived-strike 自己的逐目標演出/hit-event SFX 迴圈(§6.5 已完整反組譯出機制,但 remake 未接線 renderer/SFX/UI)、id30 在「native command」系統的 cursor line-selector 特殊目標選取邏輯與 `applySpell` 的一般 AoE 目標選取邏輯不同步(兩套子系統維持各自的目標選取實作,不視為缺陷,只是分工邊界)、id31 的玩家可見名稱與確切遊戲定位仍未知(`command_labels.json` 該 slot label 為空字串,只知道它與其餘四招共用相同的傷害/命中機制)。此項(傷害實裝)本身視為已關閉。

**`0x2d80d`(`FUN_0002d80d`,body `0x2d80d..0x2df00`,1780 bytes,ID32-35『四類特殊演出』)**——逐指令反組譯+decompile 確認內部依 `commandId` 精確分四支,對照 `docs/data/command_labels.json`(32=熾天使、33=風妖精、34=破壞神、35=暗邪鬼)與 `docs/knowledge-base/02-game-data-reference.md` 攻略文字逐支核對:

| id | 名稱(`command_labels.json`) | `0x2d80d` 內呼叫的 callee | doc02 攻略文字 | 一致? |
|---|---|---|---|---|
| 0x20(32) | 熾天使 | `FUN_0002111a(0x20, targetArray, targetCount)`(item type21 共用同一入口,終端經 `0x1c75e`) | 「召喚(最強攻擊)」 | ✓ 定性一致(固定強攻 relay) |
| 0x21(33) | 風妖精 | 逐 target 先 `memset(target+0x25, 0, 3)`(清 `+0x25/+0x26/+0x27` 三個狀態欄位)→ `FUN_000211a4(0x320=800, targetArray, targetCount)`(終端經 `0x1c916`) | 傷害欄「800」「720-799」固定值區間 | ✓ `0x320`=800(十進位)精確吻合 |
| 0x22(34) | 破壞神 | 依序 `FUN_00022721`(魔刃/AP+15%)→`FUN_00022866`(魔鎧/DP+15%)→`FUN_00022997`(風行/HIT+15,EV+15),每次呼叫間 `DAT_00053ec4=0` | 「同時施魔刃術+魔鎧術+風行術」 | ✓ 三重印證(位址+呼叫順序+攻略文字)精確吻合 |
| 0x23(35) | 暗邪鬼 | 依序 `FUN_00022d1b`(狀態施加共用核心)三次,record id 依序 `0x25`(=毒,對應 command26 毒擊術)、`0x27`(=封咒,對應 command22 封咒術)、`0x26`(=麻痺,對應 command27 麻庫術) | 「同時施麻痹術+封咒術+毒擊術」 | ✓ 三重印證精確吻合 |

四支各自在一個「`iVar5` 從 1 數到 `*pbVar6`(FDOTHER 資源自帶的 frame/sub-count byte)」的逐幀演出迴圈裡,於特定 frame 觸發一次額外 SFX:id 0x21 在 `iVar5==6`、id 0x22 在 `iVar5==2` 觸發 `play_sfx_a`(`0x25a96`);id 0x20/0x23 在 `iVar5==1` 觸發 **`play_sfx_b`**(`0x25b45`,允許與 handle A 疊播)。這與已知的「`play_sfx_a`/`play_sfx_b` 呼叫端固定 3-push 慣例(table_ptr/index/priority)」ABI 完全吻合(原始反組譯核對:`PUSH 0x1; PUSH 0x1; PUSH [0x54153]; CALL 0x25a96`)。

**第二段 FDOTHER.DAT SFX index 來源——doc36 round12「id≥0x20 分支自己的 index 來源未追出」本輪追出並關閉**:原始反組譯 `0x2d981..0x2d985` 確認 `movzx eax, byte ptr [ESP + commandId*0x1 - 0xc]`——**`commandId` 本身(0x20-0x23 全值,不是 `id-0x20`)直接當 byte offset**,落在函式序言把單一全域 `DAT_00052668`(一個 dword)存入的 4-byte 堆疊區內(`MOV EAX,[0x52668]; MOV [ESP+0x14],EAX`,而 `commandId-0xc` 對 `id=0x20..0x23` 正好等於 `ESP+0x14..0x17`,即這個 dword 的 4 個 byte)。用 `bytes` action 直接 dump `0x52668`:`5b 5c 5d 5e`(十進位 91/92/93/94)。已用 `tools/export_sfx.py --res {91,92,93,94}` 逐一解包驗證:四個都是合法的巢狀 `LLLLLL` SFX 容器(91/94 各 4 個 sub-sample、92/93 各 3 個,sub0 皆為同一份 6561-byte 共用揮擊音,與 doc36 round12 記錄的 `#82-90` 家族結構完全同構),resource 編號緊接在已知的 `#82-90`(action_id 0-9 物理攻擊 SFX 池)之後、連號 91-94,四個 WAV 已匯出至 `remake/assets/sfx/battle_{91,92,93,94}_{00,01,...}.wav`。第一段 FDOTHER.DAT index(`commandId+0x21`,即 resource 65-68)未逐一解包驗證型態,推定是配合演出的貼圖/BG 類資源而非 SFX,留待需要時再展開。

**與舊文件的關係(位址勘誤,非新結論)**:`docs/knowledge-base/56-fd2-remake-sdd.md`(2305-2311 行、852-855 行)與 `docs/knowledge-base/SESSION-HANDOFF-2026-07-06.md`(554 行)在 2026-07-26 已經記過幾乎一模一樣的 ID32-35 呼叫序列,但當時標的位址是已知錯誤的 `0x27fc9`(`0x27fc9` 實際是無關的選單方向鍵游標函式 `FUN_00027f4a`,見 `known_address_errata.json` 既有 `0x27fc9`→`0x2ff01` 勘誤條目)。本輪在**正確位址** `0x2d80d` 重新獨立反組譯,結論與舊文件幾乎逐字吻合——視為對舊(誤標位址)結論的獨立重新確認,不是推翻;已在 `known_address_errata.json` 補一筆專門條目區分「總派送函式勘誤」與「ID32-35 複合 handler 勘誤」這兩件不同的事,避免未來讀者把兩者混為一談。

**尚未展開(誠實列出)**:derived-strike(`0x2cf30`)hit-event 陣列(`FUN_000314de` 回傳)逐 byte 語意;`0x2d80d` 兩個色票全域(`DAT_0005265c/60/64`,供 `FUN_0002df01` 呼叫用,推測是揮動/爆閃效果的顏色參數)未鑑定;第一段 FDOTHER index(resource 65-68)型態未解包驗證;remake 尚未接上 ID24/28-31 的演出/SFX 迴圈與 ID32-35 的四分支邏輯(僅接了 ID24 的傷害公式,見 doc42 gap audit)。

### worklist L555/L557/L572 完成度

- **L555**(doc56 L600:scroll/composite/專用演出/SFX/UI 未接):`FUN_0002ff01` 的逐目標迴圈證實了 scroll/composite 的原生結構(`FUN_00011eb0`/`FUN_0002eb9f`/`FUN_000311e5` 等 step 呼叫,HP 從 `iStack_38` 動畫過渡到 `iStack_50`),但 renderer/SFX/UI 仍未接進 remake——**部分推進,未關閉**。
- **L557**(AoE range>0、命中率):命中率——**本輪以 code-level 反編譯二次核實,確認與物理 HIT−EV 完全獨立,可視為結論穩定**(逐 ID 數值核對仍缺,見 §6.1)。AoE——**2026-08-20 續輪(§6.4)已用位址級反組譯完整追出上游生成器**:`FUN_00014818` 依 spell/item record 的 `[+3]`(選取範圍)/`[+4]`(生效範圍)兩個 byte 欄位,分流成「`FUN_0004e390`+`FUN_0004e42c` 遞迴 flood fill 塗地圖緩衝區」(圓形/範圍型,`<0x10`)或「列/欄門檻掃描」(直線型,`>=0x10`),再掃描全部 unit 依緩衝區命中+`[+6]` 陣營篩選收集成 `FUN_0002ff01` 的 `param_3/param_4`——**鏈路完整,已關閉**(僅剩葉節點 `FUN_0004e4be`/`FUN_0004e8a5` 的資料表細節未展開,不影響機制結論)。
- **L572**(doc37 結論、`0x2a6bd` command-specific presentation/SFX/命中分支):doc37 的 spell-id 不選 FIGANI 結論本身不受影響,仍成立。`0x2a6bd` 位址勘誤(§6.3)是先前一輪最主要產出:command-specific presentation dispatcher 的**真正位址**現為 `0x2ff01`,其分支結構(id 0–8 走 AoE 迴圈、id 24/28–31 走 `0x2cf30`、id≥32 走 `0x2d80d`)首次有反組譯佐證。**本輪(§6.5)進一步把 `0x2cf30`/`0x2d80d` 兩個 callee 逐指令展開**:derived-strike 倍率表訂正(30/31 共用 18)+ 自己的 hit-event SFX 迴圈、ID32-35 四分支語意逐支對上 command_labels.json+doc02 攻略文字、doc36 round12 遺留的「id≥0x20 index 來源未追出」缺口關閉(`DAT_00052668`=[91,92,93,94])——**位址勘誤、大方向分支、兩個 callee 內部邏輯與逐 command SFX index 均已解;仍未展開的只剩 hit-event 陣列 leaf-level 語意與 remake 演出/SFX 接線,結構性理解視為已關閉,執行層 SFX/renderer/UI 完整 presentation contract 仍未展開**。

## 8. `+0x22/+0x23/+0x24` 不是 DX/race/multiplier——worklist L368/570/571/609 措辭勘誤複核(2026-08-24)

> 背景:`91-worklist.md` 現行第 570/571/609 行(戰後 town/整備流程、class-change church 兩段)仍把
> unit record `+0x22/+0x23/+0x24` 稱為「DX/race/multiplier 欄位」並列為待資料化項目。本輪純靜態複核
> (讀 `docs/knowledge-base/13-battle-menu-system.md`、`docs/knowledge-base/32-item-combat-stats-re.md`
> §4.3、`remake/internal/battle`,未跑新 Ghidra query)確認:**這個欄位語意早在 2026-08-19 就已完全
> 反組譯並資料化,「DX/race/multiplier」是過時措辭,不是真正開放的 RE 缺口。**

### 8.1 真正語意:command17/18/19 暫態 buff 持續時間 byte,不是角色屬性

`doc13`(`13-battle-menu-system.md`「native commands 17..19 殘留缺口收斂」節)與 `doc32` §4.3(L368)
已交叉反組譯確認:

| offset | 對應 command | 法術 | 效果 | 到期文字(FDTXT_000) |
|---|---|---|---|---|
| `+0x22` | 17 | 魔刃術 | AP+15%(寫 `+0x48`) | idx0x1E1「增加攻擊力的效果消失了！」 |
| `+0x23` | 18 | 魔鎧術 | DP+15%(寫 `+0x4A`) | idx0x1E2「增加防禦力的效果消失了！」 |
| `+0x24` | 19 | 風行術 | HIT+15,EV+15(寫 `+0x4C/+0x4E`) | idx0x1E3「增加速度的效果消失了！」(文字比喻,機制上不動 MV) |

寫入端 `0x22721`/`0x22866`/`0x22997`(施法命中時各自 `+= rand()%4+2`)、遞減端 `0x1A866`(每回合逐 byte
`DEC`,歸零才顯示到期文字並呼叫 `0x1B750`)、重算端 `0x1B750`(非零才把 AP/DP 乘 1.15 或 HIT/EV 各加 15,
寫回 `+0x48/+0x4A/+0x4C/+0x4E`,而非對稱減法)三段呼叫鏈已逐指令反組譯釘死。這與 `+0x25/+0x26/+0x27`
(中毒/麻痺/封咒到期)共用同一個 `0x1A866` decrement 迴圈與到期訊息呼叫序列,但只有 index0-2(即
`+0x22..+0x24`)緊接著呼叫 `0x1B750` 重算 derived stat。

**跟 DX、race 完全無關**:`+0x22/+0x23/+0x24` 落在已知 `0x50`-byte unit record 裡,而 raw
race/class/level 三個 byte 是 `+0x1F/+0x20/+0x21`(見 `26-per-chapter-event-handlers.md` L279、
`45-class-name-mapping.md`)、raw AP/DP/DX 各自的 effective word 也不在這三個 offset——兩組欄位在
record 佈局裡本來就不重疊,「DX/race/multiplier」的舊猜測沒有位址證據支持。`doc32` §4.3 額外確認過
另一個容易混淆的候選(`0x602ad` 道具表,215 rows、stride `0x17`=23)也不可能是這三個 offset 的來源,
因為 `0x22`(34)已經超出該表單行 23-byte 的範圍。

### 8.2 靜態資料值:所有已知地圖資產在這三個 offset 上恆為 0(這是設計本身,不是資料缺口)

`+0x22/+0x23/+0x24` 是**純 runtime 暫態欄位**,只在戰鬥中施放魔刃/魔鎧/風行命中後才被寫非零值;
在任何 persistent/存檔前的靜態角色資料裡沒有意義,`doc56`(2026-08-19)已記錄現有 33 張地圖資產的
`native_transient` 陣列(即這三個 byte 加上 `+0x25/+0x26/+0x27`)**全數為 0**。因此「查明這三個 offset
對每個 unit/character 的靜態值」這個問題本身答案是明確的——恆為 0,原版沒有任何角色會在關卡開始時
自帶魔刃/魔鎧/風行 buff。不需要、也不可能再從 EXE 的角色資料表裡"多挖出"一批非零值。

### 8.3 remake 現況:資料層三個 primitive 都已存在,只是還沒串成可執行指令

`remake/internal/battle` 已有三個各自獨立、有測試覆蓋的 raw-ABI primitive,逐位元組對映上述三段
原生邏輯:

- `battle.ApplyNativeCommandModifier`(`native_command_modifier.go`)— 對映 `0x22721/0x22866/0x22997` 的
  施法命中寫入(`__CHP` 朝零、`rand()%4+2` duration)。
- `battle.ApplyNativeRuntimeEquipmentRecalc`(`native_equipment.go`)— 對映 `0x1B750` 的 1.15/朝零/+15
  條件式 derived-stat 重算。
- `battle.TickNativeTransientsRaw`(`native_transient.go`)— 對映 `0x1A866` 的逐 byte decrement + 歸零
  回報 expiry。

**三者彼此沒有被串接**(`doc13` 已指出):沒有等價於 ID20/21/22/26/27 已有的
`ExecuteNativeCommandClearRestore`/`ExecuteNativeCommandApplication` 的 `ExecuteNativeCommand17_19`
command executor(target 解析 + `0x1CA89` MP debit + 呼叫 `ApplyNativeCommandModifier` 寫 duration);
且即使接上,`TickNativeTransientsRaw` 目前也不會在 expiry 時呼叫 `ApplyNativeRuntimeEquipmentRecalc`。
這是真正剩下的落差,但屬於**引擎整合(engine integration)**,不是「資料化」——資料/語意本身已經
完整反組譯並落地成可測試的 Go 函式。remake 玩家目前透過完全不同的 legacy 路徑
(`magic.go applySpell` case17/18/19 → `Unit.BuffAPPct/BuffDPPct/BuffHit/BuffEV` + 共用 `BuffTurns`)
施放並看到魔刃/魔鎧/風行效果,那是刻意簡化的可玩近似,不是這三個 native raw-ABI primitive 的串接結果。

### 8.4 結論

worklist 第 570/571/609 行的「原版 `+0x22/+0x23/+0x24` DX/race/multiplier 欄位資料化」描述**過時**:
真正的欄位語意(command17/18/19 buff duration byte)、寫入/遞減/重算三段原生邏輯、以及到期文字全部
已在 2026-08-19 完整閉合(見 `doc13`、`doc32` §4.3),靜態角色資料上的值也已確認恆為 0。唯一仍待的
工作是把已存在的三個 remake primitive 串成一個可執行的 `ExecuteNativeCommand17_19` command,那是
implementation/engine-integration 工作,不是 RE 缺口。本節不修改 `91-worklist.md`(依任務指示由外部
協調 session 同步),僅在此記錄查證結果與證據鏈供之後同步參考。
