# 42 — RE 已記錄 vs remake 已實作:落差稽核

> 目的:逐一核對「RE knowledge-base 已記錄的機制」與「remake 程式碼實際做了什麼」,列出落差與優先度。
> 方法:每項機制先讀對應 doc,再 grep/讀 `remake/internal/battle`、`remake/cmd/fd2` 的實作,以 code 為準,不憑印象判定。
> 2026-07-25 重新校正本表：撤回已被後續 code 推翻的「零命中／完全沒有」斷言。序章主角隊進場(staging)由另一 agent 處理,本篇不重複列。
> 狀態符號:✅已實作(含公式/資料對齊) 🟡部分(做了一半或簡化) ❌缺(RE 有記錄,remake 未做)。

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
| 物理攻擊:**命中率 (HIT−EV)%** | doc02 §4.1 | 🟡已補(HIT/EV 為近似值) | `model.go EffectiveHIT/EffectiveEV` + `combat.go rollsHitPct`;**HIT/EV 兩個基礎值本身是固定近似值(export_units.py DEFAULT_HIT=90/DEFAULT_EV=5)**,因為 doc03 明確記載這是「衍生值(由上面計算,直接改無效)」而非「敵/友單位 10B」表的原始欄位,且 remake 尚無裝備系統可提供真正來源(item.json 的 hit/ev 是掛在武器/防具上)——**doc42 原敘述「只是匯出腳本未取用」不完全準確,實際是來源表本身缺這兩欄**,見 export_units.py 檔頭更正說明 | 中(HIT/EV 真值待裝備系統) |
| 物理攻擊:**傷害隨機化(0.9×max~max−1)** | doc02 §4.1 | ✅ | `combat.go AttackWithRNG` 呼叫 `magic.go randomizeAmount`(與法術共用同一公式) | — |
| native IDs24/28/29/31 derived strike | SDD56 UI-03 | 🟡 strict state-only | `ExecuteNativeCommand24`／`ExecuteNativeCommandDerivedStrike` 已依 `0x276EC` 的 verified multiplier 寫 final HP delta；two-stage UI、multi-hit/SFX 未接。legacy `CastArea` 不是證據 | 高 |
| normalized spell attack/heal/hit | doc02；legacy `magic.go` | 🟡 approximation | `CastArea` 有可玩結算，但 native command ID、target geometry、effect family 和 renderer 沒有逐項閉合；不得以其數字證明原版法術完成 | 高 |
| native IDs17–19 modifier | SDD56 UI-03 | ❌ engine fail-closed | 已驗 `+0x22..+0x24` raw writer／duration 與 `__CHP` toward-zero，唯 derived-base/equipment recompute、presentation 未作 adapter；不能把 legacy Buff 視為同一機制 | 高 |
| native IDs20–22、25–27 clear/application | SDD56 UI-03 | 🟡 strict state-only | 已有 raw clear/application executors；status name、native UI、完整 tick/expiry 對照未閉合 | 高 |
| native ID23 relocation | SDD56 UI-03 | ❌ | `0x2218A→0x22253` 是特殊 selector＋indexed presentation；不等同 normalized teleport，保持 fail-closed | 中 |
| native IDs32–35 compound | SDD56 UI-03 | ❌ | static helper order 已知，但 MP transaction、rollback、UI/SFX 未閉合；禁止以 legacy combo 實作宣稱完成 | 高 |
| 經驗值公式(攻擊/恢復/各系術) | doc02 §4.5 | 🟡 normalized approximation | legacy `growth.go`／`CastArea` 的獎勵不證明 native command 逐 ID 的 EXP route；IDs22/32–35 等仍缺原版 transaction/effect evidence | 高 |
| 升級(每 100 經驗一級、成長亂數) | doc02 §2/§4.6/§7.2 | ✅已補(worklist 第 9 輪) | `growth.go GainExp`/`applyLevelUpGrowth`,門檻 100(doc03 0x43),可連續跨級;`growthTable` 為 doc02 §7.2 顯示值與 EXE 升級成長表(`docs/data/exe_tables/growth.json` 0x55EA1)交叉比對後的精確版(63 列全比對成功,見該檔案頭註解),非估計值。`Unit` 新增 `Exp`/`ExpPerLevel`/`DX` 欄;`ExpPerLevel`(攻擊經驗公式的「守方每級經驗」)來源 EXE 敵/友單位表,由 `export_units.py` 新增 `ex` 欄接上,34 份本機 `map*_units.json` 資產已重新匯出;查無成長資料的單位(如無名雜兵)等級仍照門檻演進但不套用屬性成長,誠實標記非靜默丟棄。**升級是否立即回滿新增 HP**doc 未明講,採較合理的 RPG 慣例並於 `growth.go` 註解誠實標記為假設 | — |
| 敵方 AI:目標評分(dmg、擊殺加成×2) | doc11 | 🟡 | `combat.go aiActUnit/NextAIPlan`:已套地形 AP/DP%、並依原版證據加入 **dmg≤2 略過**；擊殺加成仍是 remake 簡化版(`dmg≥HP→score×2+1000`)，**情境加成(0x1529E)、狀態倍率×1.5(0x152AB)** 尚待 RE | 中 |
| 敵方 AI:**施法決策**(法師/僧侶主動用攻擊術/補血術) | direct disasm 已證實：`0x15688` 枚舉 command，`0x1579A–0x157B5` 對 `command>0x0F` 以 `spell_id=command-0x10` 評分；`0x150D3–0x150F1` 執行同一 spell command，`0x15168→0x28784` 播放施法演出；`0x15B77` 依 spell family 分流目標評分 | 🟡 | remake 已有 `AICommandSpell`、`AIAvailableSpells`、`AISpellCandidates` 與 `AIPlan.SpellID`，但 `NextAIPlan` 仍未把 spell score/target/execute 接完；不能再寫成「完全沒有保存 SpellID／恆為純物理」 | 高；補 native ranking、MP/command gate、runtime Cast |
| 敵方 AI:**使用道具** | doc11 未記錄此分支(doc11「仍待確認」清單也未提道具);doc02 未給 AI 道具規則 | ❌(RE 亦未記錄機制) | `aiActUnit` 無任何道具邏輯;RE doc11 本身也沒有「AI 用道具」的反組譯條目——這條是 RE 與 remake 雙缺,非「RE 有記 remake 沒做」 | 低(先確認原版是否真有此行為,再排 RE 工作) |
| 移動地形成本(森林/沼澤耗 MV) | doc02 §3.1 | ✅ | `move.go MoveCost` 讀 `map.json` 的 `cost` 陣列(worklist 第8輪「地形屬性接線」) | — |
| **地形攻防加成** | native `0x1acf3`、`0x51a12/0x51a2a` | ✅原版逐格資料 | 同上「物理攻擊:地形 AP/DP% 修正」條：完整 raw map 直接用 FDSHAP control byte+1；0→(+5,0)、1/5→(0,0)、2/3→(-5,+10)、4→(-5,-5)。這取代 doc02 對一般地面 DP-5 的舊摘要；Cost 僅是 legacy fallback。 | 低 |
| 裝備欄 / 裝備加成 AP/DP/HIT/EV | doc02 §5、doc32 §1/§5 | 🟡 | `Unit` 有 `Inventory`/`Equipped`/`InventorySlots`；`campaign.EquipItem`、`RecomputeEquipment` 與 shop equip UI 已接線。HIT/EV 真值與戰鬥全鏈仍需對照原版欄位，不能再說「無裝備欄」 | 高；補 native stat source 與 battle integration |
| 道具使用效果(藥水回血、卷軸) | doc02 §5.13 | ❌ | battle action 的 item command 仍是未實作入口；但 inventory/reward/shop/equip 並非全缺 | 高 |
| 裝備自帶法術(不耗MP、無經驗) | doc02 §4.6、doc32 | 🟡 | 裝備資料與裝備重算已存在，裝備法術在 `Cast`/action menu 尚未接成獨立不耗 MP 路徑 | 中 |
| 轉職系統(Lv20+教會、轉職道具→最高職業) | doc02 §7.1、doc32 §4「[阻] 轉職系統」 | 🟡 | `church` UI、`ClassChangeCandidates`、`ApplyClassChange`、growth table 已存在；native eligibility/fee/所有分支仍需 RE，不能再寫成 remake 零命中 | 中 |
| legacy 中毒/麻痺/封咒與 Buff 的回合處理 | doc02 §6.4 | 🟡 normalized approximation | `model.go TickStatus`,`main.go:1962` 每回合結尾呼叫；但 native `0x1A866` 實際對 raw `+0x22..+0x27` 逐 camp、逐 byte 遞減，只有歸零才重算，尚不能宣稱 `TickStatus` 的 named status／每回合語意等同原版 | 高（native transient/UI/expiry recompute） |
| legacy 中毒每回合 −10% HP | doc02 §6.4 | 🟡 normalized approximation | `TickStatus` 使用 `dmg := u.MaxHP/10`；現已知 native command transient `+0x25..+0x27` 不能直接命名為 legacy Poison/Paralyze/Seal，故此不是原版 native status closure | 高 |
| legacy Buff(魔刃/魔鎧/風行)到期清除 | doc02 §6.4 | 🟡 normalized approximation | `TickStatus` 的共享 `BuffTurns` 歸零清空；native IDs17..19 則分別寫 `+0x22/+0x23/+0x24`、2..5 camp phases、並依 `0x1B750` 重算衍生值，shared timer 不等同原版 | 高 |
| 對話嘴型動畫(m0閉/m3開,doc14 0x16d00) | doc14、doc40 | 🟡 | `main.go`/`internal/dato.MouthState` 已對齊每 2 frame、開嘴 1 tick、`rand()%30+2` cadence，並可載入四幀 DATO；但 `0x168b6` dialogue-frame/grid、完整 resource binding、speaker layout 與 runtime dialogue parity 尚未閉合，不能列為完整 ✅ | 中 |
| 法術施放演出(命中/傷害畫面) | doc35、doc37 | 🟡 approximation | remake 攻擊型法術(`sp.Target==0`)重用 `newAtkAnim`，治療型只有文字；這是目前 runtime 缺口，**不是原版「無獨立法術特效」的結論**。原版僅證實 `0x28784` 不以 spell-id 選另一段 FIGANI；`0x2a6bd` command presentation dispatcher 與命中／效果層仍待閉合。 | 中(補 native presentation/effect path) |
| 商店(一般商品) | doc13 | ✅ | `main.go` `case "shop"`,`ShopGoods()`,購買扣金流程 | — |
| 祕密商店(旗標條件開啟) | doc13、campaign.go `SecretIf` | ✅ | `campaign.go:50` `SecretIf`;`ShopGoods()` 依旗標回傳 `Secret` 清單(commit e09c68c 已完成) | — |
| 商店賣出(原價 75 折) | doc02 §4.6 | 🟡 | `campInput` shop sell mode、`campaign.SellSlot`、price×3/4 與 inventory/equipment recompute 已實作；原版 menu/cancel semantics 尚未 E2 驗證 | 低 |
| 存檔/讀檔 | doc19 | ✅(自有格式,非破解 FD2.SAV,已在 save.go 註明是刻意設計) | `save.go` 存 campaign 節點/旗標/金幣/道具 | — |
| BGM 播放 | doc12 | ✅ | `audio.go playBGM`,同曲不重播/換曲釋放語意對齊 `0x26777` | — |
| SFX(命中/陣亡/選單音) | doc36 | ✅(池對照為近似值,doc36 已註記真實 attack_id→sfx 池對照未 RE 完成) | `audio.go loadSFX/playSFX`,`main.go` 多處呼叫 | — |
| 出場人數上限(前27章16人/末3章20人) | doc02 §4.6、native `0x318ad` | 🟡 | remake 已把 raw 勾選表的 selection cap 資料化為一般 `party_limit=15`、末路線 `party_limit=19`，並由 preparation UI/測試套用；這是 native 0-based cap 的目前證據，不把顯示人數 16/20 與內部上限混為同一欄。仍待完整 native deployment cursor／overflow 行為與實機 UI 對照 | 中 |

## RE 側也需要補的缺口(非 remake 落差,附帶記錄)

- **施法入口已找到**：`0x154D1` 仍不是入口；`0x15688/0x157B5` 的 AI command 評分、`0x15B77` 的 spell-family 目標分支與 `0x15055/0x150F1` 的 spell 執行 callsite 已定案。runtime `unit+0x1a..+0x1d` 是 magic raw，`+0x22..+0x24` 只保留 raw transient/modifier bytes，不是 M1–M5 bitfield，也不命名成 AP/DP/HIT/status。remake 缺口是 command inventory、SpellID、治療／攻擊目標優先級與 runtime execution 尚未接完。
- **doc32 §4 三個 `[阻]` 項目(裝備加成精確公式、物品使用效果碼、轉職系統機制)本身就還沒反組譯完**,remake 的裝備/道具/轉職缺口有一部分要等 RE 補完才能對照實作,不能單純算「remake 沒做」。

## 已移除的歷史統計與排序

早期的 33 項計數、worklist 第 8 輪增減帳與「前 5 項」排序已被後續程式與 RE 證據取代，
會與上方逐列現況互相矛盾，故不保留在本文件。需要歷史 provenance 請查 Git；當前優先序
由 `56` SDD 的 evidence gate、`57` UI matrix 與 `91` worklist 決定。
