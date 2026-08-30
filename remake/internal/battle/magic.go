// magic.go — 法術系統(doc 02/03/13):法術表 = EXE dump(spell.json,36 條)。
// Names/order are an editable normalized mapping; native unit+0x22..0x24
// are modifier flags, not M1–M5 spell bitfields (see doc03/direct constructor trace).
//
// 公式依據(docs/knowledge-base/02-game-data-reference.md §4/§6,青衫攻略 notes.md/spell.md 交叉驗證):
//   - §4.3 法術攻擊傷害:實際傷害 = 最大傷害 × 0.9 ～ 最大傷害-1(亂數,無條件捨去)。
//     已用 spell.json 實際數值核對(如 id0 火炎 dmg=50 → 45–49、id13 治療 dmg=70 → 63–69、
//     id9 咒殺 dmg=999 → 899–998),與 doc02 §6.1/§6.3 列出的區間逐條吻合,判定公式可信。
//     魔法抗性欄位尚未進 units.json/doc03 資料管線,先以 0(不打折)計,標記待補。
//   - §4.4 恢復法術:同一隨機公式,套在 target=1 的治療型法術(治療/回復/再生/神恩/風妖精)。
//   - §6.4 輔助法術效果:魔刃 AP+15%、魔鎧 DP+15%、風行 HIT+15/EV+15,持續 2–4 回合(doc 原文;
//     不是先前規格草案猜測的「風行 MV+2」,查得明確依據後改採 doc02 數字)。
//     解毒/祛麻/封咒/行動術/毒擊/麻痺/傳送/破壞神/暗邪鬼依 doc02 §6.4 逐條实作,細節見 applySpell 內註解。
//   - 命中率:doc02 §4.3「命中率=法術內定命中率」→ 用 spell.json 的 hit 欄擲骰
//     (native FUN_0001c75e:`record[+2] <= roll(0..99)` 才 miss,hit=0 時恆進入 miss 分支——
//     見 docs/knowledge-base/27-combat-rules-and-validation-checklist.md §6.6 逐位元組核對,
//     2026-08-30 修正:此欄先前誤植為「hit<=0 一律視為必中」,方向與原生相反,已訂正,見 rollsHit)。
//     少數 id 的原生命中判定完全不經過這個 7-byte hit 欄/FUN_0001c75e,細節見 rollsHit 函式註解:
//     - id22(封咒術)、id35(暗邪鬼,內含封咒/毒擊/麻痺三重狀態)實際走 `0x22d1b` 狀態施加核心,
//       固定 50% RNG gate,與 record[+2] 無關(id22 dump 值為 0,id26/27 為 50 純屬巧合,見
//       docs/knowledge-base/32-item-combat-stats-re.md:442-483、native_item_marker_application.go)。
//     - id24/28/29/30(劍技)、id31(未知)實際走 `0x2cf30` derived-strike,完全不呼叫任何命中判定,
//       固定套用倍率傷害(對應 doc02「劍技恆中」),見 §6.5。
//   - §4.2 劍技傷害:2026-08-30 續輪接上——`AP×倍率(15/20/12/18)/10 − DP` 已由 native 0x2cf30
//     完整反組譯確認(§6.5),applySpell 直接呼叫既有、已測試的
//     native_command24.go ResolveNativeCommandDerivedStrikeDamage,不重寫傷害公式,見
//     derivedStrikeMultiplier 與 applySpell case 24/28/29/30/31 的註解、§6.6.1 收尾記錄。
package battle

import (
	"encoding/json"
	"math/rand"
	"os"
	"time"
)

// Spell 一條法術(spell.json 欄位)。Target:0=敵方(傷害/攻擊性效果)、1=我方(治療/輔助)、
// 其他值(目前只有 23 傳送術=3)=特殊定位類,不掃場上單位。
type Spell struct {
	ID     int `json:"id"`
	Dmg    int `json:"dmg"`
	Hit    int `json:"hit"`
	Dist   int `json:"dist"`  // 施法距離
	Range  int `json:"range"` // 波及範圍(0=單體)
	MP     int `json:"mp"`
	Target int `json:"target"`
	Name   string
}

// spellNames is a legacy normalized presentation list used by the current
// gameplay approximation. It is not the native label source: IDs 0..35 are
// now byte-identical to the EXE command-record/spell table and their original
// text lives in docs/data/command_labels.json (FDTXT_000). Keep this list
// separate until the native command selector replaces the legacy spell menu.
var spellNames = [36]string{
	"火炎", "烈炎", "炎龍", "天火", "電擊", "落雷", "轟雷", "神雷",
	"聖光彈", "咒殺", "碎岩", "地震", "裂地", "治療", "回復", "再生",
	"神恩", "魔刃", "魔鎧", "風行", "解毒", "祛麻", "封咒", "傳送",
	"破龍擊", "行動術", "毒擊", "麻痺", "淒煌斬", "熾炎刀", "音速刃", "?",
	"熾天使", "風妖精", "破壞神", "暗邪鬼",
}

// LoadSpells 讀法術表(EXE dump 的 spell.json)並補名稱。
func LoadSpells(path string) ([]Spell, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var sp []Spell
	if err := json.Unmarshal(raw, &sp); err != nil {
		return nil, err
	}
	for i := range sp {
		if sp[i].ID >= 0 && sp[i].ID < len(spellNames) {
			sp[i].Name = spellNames[sp[i].ID]
		}
	}
	return sp, nil
}

// InCastRange 目標格是否在施法距離內(曼哈頓距離 ≤ Dist)。
func (s *State) InCastRange(u *Unit, sp Spell, tx, ty int) bool {
	dx, dy := tx-u.X, ty-u.Y
	if dx < 0 {
		dx = -dx
	}
	if dy < 0 {
		dy = -dy
	}
	return dx+dy <= sp.Dist && dx+dy > 0
}

// CastResult 一次法術對單一目標的結算結果。
type CastResult struct {
	Target *Unit
	Amount int // 傷害或治療量(正值);Miss 或無數值效果(如純狀態施加)回 0
	Missed bool

	// ExpGained/LevelUps:施法者這整次施法(可能命中多個目標)總共取得的經驗值/升級事件
	// (doc02 §4.5;見 growth.go、awardCastExp)。同一次 CastArea 呼叫回傳的每筆 CastResult
	// 都帶相同的彙總值(不是逐目標拆分),方便呼叫端(main.go)只看第一筆或任一筆都能取得。
	ExpGained float64
	LevelUps  []LevelUpEvent
}

// engineRand 供舊版 Cast() 相容介面使用的內部亂數源(引擎呼叫此簽名時未注入 rng)。
// 測試/需要可重現結果一律走 CastArea 並自行注入 *rand.Rand。
var engineRand = rand.New(rand.NewSource(time.Now().UnixNano()))

// buffRoll 輔助法術效果持續回合數(doc02 §6.4:2–4 回合)。
func buffRoll(rng *rand.Rand) int { return 2 + rng.Intn(3) }

// randomizeAmount 依 doc02 §4.3/4.4:實際值 = 最大值 × 0.9 ～ 最大值-1(亂數,含端點,無條件捨去)。
// max<=0(如純狀態類法術的 dmg 欄)回 0。
func randomizeAmount(max int, rng *rand.Rand) int {
	if max <= 0 {
		return 0
	}
	lo := max * 9 / 10
	hi := max - 1
	if hi < lo {
		hi = lo
	}
	return lo + rng.Intn(hi-lo+1)
}

// rollsHit 命中判定(2026-08-30 訂正方向,見檔頭註解與
// docs/knowledge-base/27-combat-rules-and-validation-checklist.md §6.6)。
//
// 一般情況對映 native FUN_0001c75e:`record[+2] <= roll(0..99)` 才 miss,故 hit<=0
// 時 roll∈[0,99] 恆滿足條件,恆進入 miss 分支——換言之 hit<=0 一律視為必不中(不是必中),
// hit>0 才擲骰(rng.Intn(100) < hit)。
//
// 兩個 id 有實機反組譯佐證,證明它們的原生命中判定根本不經過 FUN_0001c75e/record[+2],
// 故不適用上述通則,個別特例處理(不是猜測,是已知另一條命中機制的正確機率):
//   - id22(封咒術)、id35(暗邪鬼組合技,內含封咒/毒擊/麻痺):實際呼叫 `0x22d1b` 狀態施加
//     核心,該函式內建固定 50% RNG gate,與 record[+2] 完全無關(id22 的 hit 欄 dump 值是 0、
//     id26/27 是 50,但 0x22d1b 用的是編譯期常數 50,不讀 record[+2],兩者數值巧合無因果關係)。
//     見 docs/knowledge-base/32-item-combat-stats-re.md:442-483、native_item_marker_application.go。
//     (id35 的三個狀態效果在原生端各自獨立擲骰;remake 現行 applySpell case 35 仍用單一共用
//     roll 套用三個狀態,這個簡化本輪不展開,只訂正其擲骰機率從 100% 改成正確的 50%。)
//   - id24/28/29/30(破龍擊/淒煌斬/熾炎刀/音速刃劍技)、id31(未知)：實際呼叫 `0x2cf30`
//     derived-strike 路徑,完全不呼叫任何命中判定函式,固定套用倍率傷害(對應 doc02「劍技恆中」
//     攻略文字),見 §6.5。2026-08-30 續輪:applySpell 已接上對應的傷害公式(見 applySpell case
//     24/28/29/30/31、derivedStrikeMultiplier),此 bypass 現在有真正可觀察的效果。
func rollsHit(sp Spell, rng *rand.Rand) bool {
	switch sp.ID {
	case 22, 35:
		return rng.Intn(100) < 50
	case 24, 28, 29, 30, 31:
		return true
	}
	if sp.Hit <= 0 {
		return false
	}
	return rng.Intn(100) < sp.Hit
}

// derivedStrikeMultiplier 劍技/derived-strike(id24/28/29/30/31)傷害加乘率,對映 native
// 0x2cf30 反組譯結果(docs/knowledge-base/27-combat-rules-and-validation-checklist.md §6.5:
// `if id==0x18(24) mult=15; elif id==0x1c(28) mult=20; elif id==0x1d(29) mult=12; else mult=18`,
// else 分支同時覆蓋 id==0x1e(30) 與 id==0x1f(31))。
//
// 與 native_command24.go 的 nativeCommandDerivedStrikeMultiplier 刻意不共用同一張表:該函式
// 服務「native command」cursor-driven 派送路徑,其 switch 故意不含 id30(id30 在該路徑有專屬
// line-selector 入口 ExecuteNativeCommand30,由呼叫端另外硬編 18,不透過共用 lookup);這裡服務
// spell.json/CastArea 的一般 Range/Dist AoE 施法路徑,id30 在這條路徑沒有特殊目標選取需求,故
// 直接把 30 併入這張表,不強行複用另一邊為了保護其特例入口而刻意留空的 switch。
func derivedStrikeMultiplier(id int) int {
	switch id {
	case 24:
		return 15
	case 28:
		return 20
	case 29:
		return 12
	default: // 30, 31
		return 18
	}
}

// isEnemyOf 施法目標的陣營判斷:Own 與 Ally 同一陣線,對 Enemy 互為敵方(涵蓋玩家/NPC/敵方任一方施法)。
// 不沿用 combat.go 的 hostile() — 那支只為「AI 找攻擊目標」設計(a 必須是 Enemy/Ally 才會回 true),
// 玩家(Own)施法時 hostile(Own, x) 恆為 false,不能拿來判法術合法目標,故另立此函式。
func isEnemyOf(a, b *Unit) bool {
	if a.Camp == Enemy {
		return b.Camp != Enemy
	}
	return b.Camp == Enemy
}

// Cast 舊版單體施法相容介面(引擎目前呼叫此簽名)。內部轉呼叫 CastArea,以 tgt 所在格為中心;
// 若 sp.Range>0,場上其他在範圍內的合法目標也會一併中招(AoE 生效,行為變化見交付說明)。
// 回傳值:-1=MP 不足或施法者被封咒禁止施法;其餘為對 tgt 造成的傷害/治療量(Miss 或純狀態效果回 0)。
func (s *State) Cast(caster, tgt *Unit, sp Spell) int {
	results := s.CastArea(caster, tgt.X, tgt.Y, sp, engineRand)
	if results == nil {
		return -1
	}
	for _, r := range results {
		if r.Target == tgt {
			return r.Amount
		}
	}
	return 0
}

// CastArea 以 (cx,cy) 為中心,對 sp.Range 內(曼哈頓距離)所有「合法目標」各套用一次法術效果。
// 合法目標:target=0 打敵性單位、target=1 打我方(含施法者自己)。MP 只扣一次,不足或施法者
// 被封咒(Sealed)則不扣 MP、回 nil。單體法術(Range=0)退化為只打中心格上的單位。
// sp.Target 為 0/1 以外的值(目前只有 23 傳送術=3)代表特殊定位類法術,不掃場上單位,
// 只回傳一筆無數值效果的 CastResult(定位/移動邏輯留給地圖 UI,doc02 §6.4「傳送至地圖任何地點」)。
func (s *State) CastArea(caster *Unit, cx, cy int, sp Spell, rng *rand.Rand) []CastResult {
	if caster.MP < sp.MP || caster.Sealed {
		return nil
	}
	caster.MP -= sp.MP

	if sp.Target != 0 && sp.Target != 1 {
		// 特殊定位類法術(目前只有 23 傳送術)不掃場上單位,定位邏輯留給地圖 UI(見上方註解)。
		// 傳送術經驗值(doc02 §4.5「傳送術」列)沒有真正的「受法者」可掃(現況等同施法者傳送
		// 自己),以施法者自身等級當受法者等級——這是配合現有「待實裝」定位邏輯的近似,不是
		// 完整傳送機制,見 doc42 gap 追蹤。
		exp, levelUps := 0.0, []LevelUpEvent(nil)
		if sp.ID == 23 && (caster.Camp == Own || caster.Camp == Ally) {
			exp = TeleportExp(caster.Lv, caster.Lv)
			levelUps = s.GainExp(caster, exp, rng)
		}
		return []CastResult{{Target: caster, Amount: 0, Missed: false, ExpGained: exp, LevelUps: levelUps}}
	}

	var results []CastResult
	for _, u := range s.Units {
		if !u.OnField || !u.Alive() {
			continue
		}
		if manhattan(u.X, u.Y, cx, cy) > sp.Range {
			continue
		}
		wantEnemy := sp.Target == 0
		if isEnemyOf(caster, u) != wantEnemy {
			continue
		}
		results = append(results, s.applySpell(caster, u, sp, rng))
	}

	if caster.Camp == Own || caster.Camp == Ally {
		exp := awardCastExp(caster, sp, results)
		levelUps := s.GainExp(caster, exp, rng)
		for i := range results {
			results[i].ExpGained = exp
			results[i].LevelUps = levelUps
		}
	}
	return results
}

// awardCastExp 依 doc02 §4.5 逐條公式,把一次 CastArea(可能命中多個目標)的經驗值加總
// (見 growth.go 檔頭表)。封咒術(22)、破壞神(34)、暗邪鬼(35)doc02 沒列經驗公式,不編造,
// 回 0——這是誠實的「文件未涵蓋」,不是漏做。
func awardCastExp(caster *Unit, sp Spell, results []CastResult) float64 {
	switch sp.ID {
	case 17, 18, 19: // 魔刃術/魔鎧術/風行術:2 × Σ(受法者等級/施法者等級)
		sum := 0.0
		for _, r := range results {
			if r.Missed {
				continue
			}
			sum += buffExpTerm(caster.Lv, r.Target.Lv)
		}
		return 2 * sum
	case 20, 21: // 解毒術/祛麻術:Σ(40×9/受法者總HP) × (受法者等級/施法者等級)
		sum := 0.0
		for _, r := range results {
			if r.Missed {
				continue
			}
			sum += statusExpTerm(caster.Lv, r.Target.Lv, r.Target.MaxHP)
		}
		return sum
	case 25: // 行動術:8 × (受法者等級/施法者等級),單體
		for _, r := range results {
			if !r.Missed {
				return ActionExp(caster.Lv, r.Target.Lv)
			}
		}
		return 0
	case 26, 27: // 毒擊術/麻痺術:同解毒/祛麻同一公式(doc02 §4.5 兩列共用同一式子)
		sum := 0.0
		for _, r := range results {
			if r.Missed {
				continue
			}
			sum += statusExpTerm(caster.Lv, r.Target.Lv, r.Target.MaxHP)
		}
		return sum
	case 22, 34, 35: // 封咒術/破壞神/暗邪鬼:doc02 §4.5 未列公式,不編造,見函式註解
		return 0
	case 23: // 傳送術:早退路徑已在 CastArea 的特殊定位分支(sp.Target==3)處理並回傳,
		// 這裡是防禦性保留,正常流程不會走到
		return 0
	// 24/28/29/30/31(劍技/未知,derived-strike)刻意不再列在這裡:2026-08-30 本輪
	// applySpell 已接上 §6.5/§6.6.1 反組譯證實的傷害公式(見下方 case),與
	// native_command24.go ExecuteNativeCommandDerivedStrike 的既有判斷一致——
	// 「這些指令仍是透過同一個 0x1C81F 底層寫入核心造成的普通傷害,理應走一般攻擊經驗公式」
	// (該檔案已承認這是 judgment call,非逐位元組證明),故讓它們落到下面的預設「一般攻擊型
	// 法術」分支,不再特例回 0。
	}
	if sp.Target == 1 { // 一般治療:治療/回復/再生/神恩/風妖精(doc02 §4.4/§6.3)
		sum := 0.0
		for _, r := range results {
			if r.Missed {
				continue
			}
			sum += healExpTerm(r.Amount, r.Target.MaxHP, r.Target.Lv)
		}
		if caster.Lv <= 0 {
			return 0
		}
		return 40 / float64(caster.Lv) * sum
	}
	// 一般攻擊型法術(火炎/烈炎/炎龍…):doc02 §4.5 只列「攻擊」一條物理攻擊公式,未另立
	// 法術攻擊經驗值條目——以同一條「攻擊」公式套用(defExpPerLv 來源與近戰攻擊相同,
	// Unit.ExpPerLevel),對死亡目標同樣視同傷害HP=總HP。
	sum := 0.0
	for _, r := range results {
		if r.Missed {
			continue
		}
		dmgForExp := r.Amount
		if r.Target.HP == 0 {
			dmgForExp = r.Target.MaxHP
		}
		sum += AttackExp(caster.Lv, r.Target.Lv, dmgForExp, r.Target.MaxHP, r.Target.ExpPerLevel)
	}
	return sum
}

// applySpell 對單一已篩選過陣營/範圍的目標套用法術效果:先判命中,再依法術 ID 分派效果。
func (s *State) applySpell(caster, tgt *Unit, sp Spell, rng *rand.Rand) CastResult {
	// doc02 §6.4:輔助/治療(target=1)不 miss;攻擊與攻擊性輔助(毒擊/麻痺/封咒等,target=0)依命中率擲骰。
	if sp.Target == 0 && !rollsHit(sp, rng) {
		return CastResult{Target: tgt, Amount: 0, Missed: true}
	}

	switch sp.ID {
	case 17: // 魔刃術:AP +15%(doc02 §6.4)
		applyBuff(tgt, rng, 15, 0, 0, 0)
		return CastResult{Target: tgt}
	case 18: // 魔鎧術:DP +15%
		applyBuff(tgt, rng, 0, 15, 0, 0)
		return CastResult{Target: tgt}
	case 19: // 風行術:HIT +15、EV +15(doc02 明文,取代先前規格草案的「MV+2」猜測)
		applyBuff(tgt, rng, 0, 0, 15, 15)
		return CastResult{Target: tgt}
	case 20: // 解毒術:清除中毒
		tgt.Poisoned, tgt.PoisonTurns = false, 0
		return CastResult{Target: tgt}
	case 21: // 祛麻術:清除麻痺
		tgt.Paralyzed, tgt.ParalyzeTurns = false, 0
		return CastResult{Target: tgt}
	case 22: // 封咒術:2–4 回合禁止施法
		tgt.Sealed, tgt.SealTurns = true, buffRoll(rng)
		return CastResult{Target: tgt}
	case 25: // 行動術:使已行動的人本回合可再次行動(doc02 §6.4)
		tgt.Acted = false
		return CastResult{Target: tgt}
	case 26: // 毒擊術:傷害 + 2–4 回合中毒(doc02 §6.4;dmg=10 經 randomizeAmount 恆得 9,對應攻略「附加 9 點傷害」)
		dmg := s.dealDamage(tgt, sp, rng)
		tgt.Poisoned, tgt.PoisonTurns = true, buffRoll(rng)
		return CastResult{Target: tgt, Amount: dmg}
	case 27: // 麻痺術:傷害 + 2–4 回合麻痺(同上,dmg=10 恆得 9)
		dmg := s.dealDamage(tgt, sp, rng)
		tgt.Paralyzed, tgt.ParalyzeTurns = true, buffRoll(rng)
		return CastResult{Target: tgt, Amount: dmg}
	case 34: // 破壞神:同時施魔刃+魔鎧+風行(doc02 §6.4 combo)
		applyBuff(tgt, rng, 15, 15, 15, 15)
		return CastResult{Target: tgt}
	case 35: // 暗邪鬼:同時施麻痺+封咒+毒擊(doc02 §6.4 combo)。
		// spell.json 此條 dmg=0(組合技本身不含固定傷害值),故只施狀態、不額外扣血;
		// 三個狀態共用同一次擲骰的回合數,貼近「同時施放」語意。
		turns := buffRoll(rng)
		tgt.Paralyzed, tgt.ParalyzeTurns = true, turns
		tgt.Sealed, tgt.SealTurns = true, turns
		tgt.Poisoned, tgt.PoisonTurns = true, turns
		return CastResult{Target: tgt}
	case 23: // 傳送術:目的地由地圖 UI 選取,battle 套件不處理定位——待實裝
		return CastResult{Target: tgt}
	case 24, 28, 29, 30, 31: // 破龍擊/淒煌斬/熾炎刀/音速刃(劍技)/31(spellNames[31]="?",語意未知
		// 但已知傷害機制與其餘四招相同,見下方倍率表)。
		// AP×加乘率−DP(doc02 §4.2「劍技:AP×劍技加乘」),native 0x2cf30 derived-strike 已用
		// 位址級反組譯完整釘死(docs/knowledge-base/27-combat-rules-and-validation-checklist.md
		// §6.5/§6.6.1):倍率 id24=15、id28=20、id29=12、id30/31 共用 18(§6.5「else 分支同時覆蓋
		// id==0x1e(30) 與 id==0x1f(31)」訂正)。傷害本體與 0.9~max-1 亂數化沿用
		// native_command24.go 的 ResolveNativeCommandDerivedStrikeDamage(該函式已服務
		// ExecuteNativeCommandDerivedStrike/ExecuteNativeCommand30 兩條「native command」派送
		// 路徑,本身已有測試覆蓋),此處直接呼叫同一個已驗證 helper,不重寫傷害公式。
		// 命中已在上方 rollsHit 以 case 24/28/29/30/31 恆 true bypass(§6.6.1),此處不再擲骰。
		// 目標選取沿用 CastArea 既有的 spell.json Range/Dist AoE 模型,不套用「native command」
		// 系統 id30 專屬的 cursor line-selector(SelectionMode>=0x10)——兩套系統目標選取邏輯
		// 本來就分開維護(見 derivedStrikeMultiplier 註解),此處不引入該特例。
		mult := derivedStrikeMultiplier(sp.ID)
		_, dmg, err := ResolveNativeCommandDerivedStrikeDamage(caster.AP, tgt.DP, mult, rng)
		if err != nil {
			return CastResult{Target: tgt}
		}
		tgt.ApplyHPDamage(dmg)
		return CastResult{Target: tgt, Amount: dmg}
	}

	if sp.Target == 1 { // 一般治療:治療/回復/再生/神恩/風妖精(doc02 §4.4/§6.3)
		heal := randomizeAmount(sp.Dmg, rng)
		if tgt.HP+heal > tgt.MaxHP {
			heal = tgt.MaxHP - tgt.HP
		}
		tgt.HP += heal
		return CastResult{Target: tgt, Amount: heal}
	}
	dmg := s.dealDamage(tgt, sp, rng)
	return CastResult{Target: tgt, Amount: dmg}
}

// dealDamage 一般攻擊型法術傷害結算(doc02 §4.3)。魔法抗性欄位尚未進資料管線,先以 0 計。
func (s *State) dealDamage(tgt *Unit, sp Spell, rng *rand.Rand) int {
	dmg := randomizeAmount(sp.Dmg, rng)
	tgt.ApplyHPDamage(dmg)
	return dmg
}

// applyBuff 疊加正面增益(doc02 §6.4:2–4 回合,重製簡化成單一共用計時器 BuffTurns;
// 取新舊回合數較大值,避免同類 buff 疊放時提早失效)。
func applyBuff(u *Unit, rng *rand.Rand, apPct, dpPct, hit, ev int) {
	u.BuffAPPct += apPct
	u.BuffDPPct += dpPct
	u.BuffHit += hit
	u.BuffEV += ev
	turns := buffRoll(rng)
	if turns > u.BuffTurns {
		u.BuffTurns = turns
	}
}
