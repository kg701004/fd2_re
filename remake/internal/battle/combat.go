// combat.go — 戰鬥結算 + 敵方 AI + 勝負(M1)。
//
// 傷害公式對映青衫/反組譯(doc 02 §4.1、doc 11、doc 27 checklist):
//
//	命中率 = (攻方HIT − 守方EV)%
//	暴擊時 DP = 守方DP/2(取整)
//	AP = AP×(1+攻方地形AP%)、DP = DP×(1+守方地形DP%)(取整,terrain.go)
//	最大傷害 = AP − DP;實際傷害 = 最大傷害×0.9 ～ 最大傷害-1(亂數,magic.go randomizeAmount)
//
// AI normalized approximation：舊 doc11 的 0x15140 地址已由 canonical recheck 撤回；
// 此處只保留 remake-owned 估值與 dmg≤2 相容行為，不宣稱 native AI parity。
// 演出動畫(FIGANI/移動)後補;此處先把邏輯層做對,讓第一關可玩。
package battle

import (
	"math/rand"
	"sort"
)

// AttackResult 一次近戰攻擊的完整結算結果(doc02 §4.1)。
type AttackResult struct {
	Amount int // 實際傷害;Miss 時為 0
	Missed bool
	Crit   bool

	ExpGained float64        // 攻方本次取得的經驗值(doc02 §4.5「攻擊」列;僅 Own/Ally 攻方會 >0,見 growth.go)
	LevelUps  []LevelUpEvent // 攻方因本次經驗值連續升級的事件(通常 0 或 1 筆,經驗值夠大可多筆)
}

// Attack 舊版相容介面(main.go 目前呼叫此簽名):結算一次近戰攻擊,回傳實際傷害
// (Miss 時回 0)。內部呼叫 AttackWithRNG,用 magic.go 共用的 engineRand。
// 測試/需要確定性結果一律走 AttackWithRNG 並自行注入 *rand.Rand(同 magic.go Cast/CastArea 慣例)。
func (s *State) Attack(a, d *Unit) int {
	return s.AttackWithRNG(a, d, engineRand).Amount
}

// AttackWithRNG 近戰攻擊完整結算(doc02 §4.1、doc27 checklist、doc11 地形修正)。
// 命中率、暴擊、地形% 修正、傷害隨機化皆對照青衫攻略 notes.md 逐條實作,詳見檔頭註解與
// terrain.go/model.go EffectiveHIT/EffectiveEV。恆標記已行動,不論命中與否
// (原版「攻擊」是一個已耗用的行動,miss 不退還行動權)。
func (s *State) AttackWithRNG(a, d *Unit, rng *rand.Rand) AttackResult {
	a.Acted = true

	// 命中率 = (攻方HIT − 守方EV)%;含風行術 HIT/EV 加成(EffectiveHIT/EffectiveEV)。
	hitPct := a.EffectiveHIT() - d.EffectiveEV()
	if !rollsHitPct(hitPct, rng) {
		return AttackResult{Missed: true}
	}

	crit := a.CritPct > 0 && rng.Intn(100) < a.CritPct

	// AP/DP 含輔助法術 Buff(魔刃/魔鎧,doc02 §6.4);暴擊先讓 DP 減半,再套地形% —
	// notes.md 公式順序:「暴擊時 DP=守方DP/2」在「DP=DP×(1+地形%)」之前。
	ap := a.EffectiveAP()
	dp := d.EffectiveDP()
	if crit {
		dp /= 2
	}
	atkAPPct, _ := s.TerrainAPDPPct(a.X, a.Y)
	_, defDPPct := s.TerrainAPDPPct(d.X, d.Y)
	ap = ap * (100 + atkAPPct) / 100
	dp = dp * (100 + defDPPct) / 100

	max := ap - dp
	dmg := randomizeAmount(max, rng)
	// 青衫「dmg≤2」是 AI「不值得打」門檻(doc11),非玩家攻擊下限;玩家命中至少造成 1。
	if dmg < 1 {
		dmg = 1
	}
	d.ApplyHPDamage(dmg)

	// 經驗值(doc02 §4.5「攻擊」列,growth.go AttackExp):致死視同傷害HP=總HP。
	// 只有 Own/Ally 攻方才計算/回報經驗值(見 growth.go 檔頭說明);Enemy 攻方 ExpGained
	// 恆為 0,不是先算出來又被 GainExp 悄悄丟棄。
	var exp float64
	var levelUps []LevelUpEvent
	if a.Camp == Own || a.Camp == Ally {
		dmgForExp := dmg
		if d.HP == 0 {
			dmgForExp = d.MaxHP
		}
		exp = AttackExp(a.Lv, d.Lv, dmgForExp, d.MaxHP, d.ExpPerLevel)
		levelUps = s.GainExp(a, exp, rng)
	}

	return AttackResult{Amount: dmg, Crit: crit, ExpGained: exp, LevelUps: levelUps}
}

// rollsHitPct 物理攻擊命中率擲骰(doc02 §4.1「命中率=(攻方HIT-守方EV)%」)。
// 與 magic.go rollsHit 現行語意一致(hit/pct<=0 皆視為必定 miss,對映 native FUN_0001c75e
// 的通則),但這裡 pct<=0 是公式算出來的合法結果(HIT 追不上 EV);magic.go 另外對 id22/35/
// 24/28/29/30/31 這幾個經反組譯證實繞過 FUN_0001c75e 的 id 有個別特例,見該檔案 rollsHit 註解。
func rollsHitPct(pct int, rng *rand.Rand) bool {
	if pct <= 0 {
		return false
	}
	if pct >= 100 {
		return true
	}
	return rng.Intn(100) < pct
}

// hostile 判斷 a 是否視 b 為攻擊對象(同一套 AI,依陣營;doc11)。
// 敵方(Enemy)打 玩家/友軍;友軍 NPC(Ally)打 敵方;玩家(Own)由人操作。
func hostile(a, b *Unit) bool {
	if a.Camp == Enemy {
		return b.Camp == Own || b.Camp == Ally
	}
	if a.Camp == Ally {
		return b.Camp == Enemy
	}
	return false
}

func abs(v int) int {
	if v < 0 {
		return -v
	}
	return v
}

func manhattan(ax, ay, bx, by int) int { return abs(ax-bx) + abs(ay-by) }

// sortedReachCells returns reach's cells in a fixed, deterministic (Y, X)
// row-major order. Go's map iteration order is randomized by the runtime
// (even across two `range` calls over an identical map within the same
// process, not merely across process runs) -- any nearest-cell scan that
// keeps the first-seen candidate on an exact tie (as several callers below
// and in native_ai_movement_fallback.go's moveToward do, matching this
// package's existing `for c := range reach { if d < best {...} }` pattern)
// silently inherits that nondeterminism whenever more than one reachable
// cell ties for best. Found via headless_battle_test.go's
// TestHeadlessBattleDeterministic in cmd/fd2 (2026-08-30): two runs from an
// identical fixed RNG seed produced different chapter-1 outcomes, traced to
// exactly this pattern. Sorting first makes the scan order fixed and
// reproducible; it does not change any comparison's outcome on a
// non-tied cell, and on a tie it deterministically prefers the
// lowest-Y-then-lowest-X cell rather than whichever cell the map happened
// to yield first.
func sortedReachCells(reach map[Cell]bool) []Cell {
	cells := make([]Cell, 0, len(reach))
	for c := range reach {
		cells = append(cells, c)
	}
	sort.Slice(cells, func(i, j int) bool {
		if cells[i].Y != cells[j].Y {
			return cells[i].Y < cells[j].Y
		}
		return cells[i].X < cells[j].X
	})
	return cells
}

// estDamage 是 remake normalized AI 估值；舊 doc11 0x15140 反組譯地址已撤回，
// 不把這個 helper 當作 native score proof：
//
//	myAP'  = myAP  × 地形AP%[u當下座標] / 100
//	tarDP' = tarDP × 地形DP%[t當下座標] / 100
//	估計傷害 = myAP' − tarDP'
//
// 只是選目標用的估值,不擲骰(不含命中率/暴擊/傷害隨機化——那些留給 AttackWithRNG 實際結算)。
func (s *State) estDamage(u, t *Unit) int {
	apPct, _ := s.TerrainAPDPPct(u.X, u.Y)
	_, dpPct := s.TerrainAPDPPct(t.X, t.Y)
	ap := u.AP * (100 + apPct) / 100
	dp := t.DP * (100 + dpPct) / 100
	return ap - dp
}

// aiTargets separates the original AI's attack candidate from its movement
// fallback.  This normalized compatibility rule ignores targets whose estimated
// damage is at most two; it is not proof that the withdrawn 0x15140 address has
// that native behavior. When every hostile target is below the threshold, the
// unit may still advance toward the nearest hostile but must not attack it.
func (s *State) aiTargets(u *Unit) (attack, move *Unit) {
	bestScore := -1 << 30
	bestDistance := 1 << 30
	for _, t := range s.Units {
		if !t.OnField || !t.Alive() || !hostile(u, t) {
			continue
		}
		distance := manhattan(u.X, u.Y, t.X, t.Y)
		if move == nil || distance < bestDistance {
			move, bestDistance = t, distance
		}
		dmg := s.estDamage(u, t)
		if dmg <= 2 {
			continue
		}
		score := dmg
		if dmg >= t.HP { // 可擊殺 → 最高優先(doc11 prio 0x12)
			score = dmg*2 + 1000
		}
		score = score*100 - distance
		if attack == nil || score > bestScore {
			attack, bestScore = t, score
		}
	}
	return attack, move
}

func (s *State) aiApproachPath(u, target *Unit) []Cell {
	dstX, dstY := u.X, u.Y
	bestD := manhattan(u.X, u.Y, target.X, target.Y)
	for _, c := range sortedReachCells(s.Reachable(u)) {
		if s.UnitAt(c.X, c.Y) != nil {
			continue
		}
		d := manhattan(c.X, c.Y, target.X, target.Y)
		if d < bestD {
			bestD = d
			dstX, dstY = c.X, c.Y
		}
	}
	return s.Path(u, dstX, dstY)
}

// aiActUnit 是重製端既有的正規化近似，不代表原版 0x14237 的完整候選、
// 地形、優先級與同分契約完整取代——**2026-08-14**:「原地是否已有可攻擊目標」
// 現在優先走 disassembly-confirmed 的 native-accurate composer
// (`ScoreNativeAI14237`,見 native_ai_14237.go/native_ai_14237_apply.go),
// 只有這個單位缺完整 raw provenance(裝備/地形/移動成本資料不全)時才退回
// 下面的 `aiTargets`/`estDamage` normalized 近似,不 regress 既有行為。
// 「原地沒有目標時要往哪裡移動」已依單位真實的 `record+0x34&0xf` mode 值分流到
// mode 0(0x14121→0x13E9C→0x13FD4)或 mode 1(0x14121→0x13FD4,無最近敵人
// fallback)的 disassembly-confirmed 原生版本,見 ApplyNativeAIMovementFallback／
// ApplyNativeAIMode1MovementFallback。兩者合計覆蓋 33 張地圖裡約 58%
// 的 AI 單位(mode0=1063、mode1=34,共 1887 筆有 raw provenance);其餘
// mode(2/3/4/5/7/8/9/10)與缺 raw provenance 的單位仍退回舊的最近可達格近似。
func (s *State) aiActUnit(u *Unit) {
	// 找重製端的近似攻擊目標；低傷害時仍保留最近單位作為移動目標,供下面
	// native 攻擊決策不可用、或 native 已權威判定無攻擊目標時的移動 fallback 使用。
	best, moveTarget := s.aiTargets(u)
	if moveTarget == nil {
		return
	}
	if best == nil {
		best = moveTarget
	}
	// 1. native-accurate 物理評分 composer 優先:ok=true 且 attacked=true 表示
	// 已經移動+攻擊完畢,這個單位的回合直接結束;ok=true 但 attacked=false 表示
	// native 已權威搜過所有可達落點、判定沒有值得打的物理攻擊,跳過下面 2 的
	// normalized 立即攻擊判定,但仍走既有的移動 fallback(3);ok=false 表示
	// 這個單位缺完整 native 資料,完全退回原本 2/3 的既有邏輯,不 regress。
	attacked, nativeAttackOK := s.ApplyNativeAI14237PhysicalAttack(u)
	if attacked {
		return
	}
	// 2. 已在攻擊範圍內(InAttackRange 依武器射程判定,doc32) → 直接打
	if !nativeAttackOK && s.InAttackRange(u, best.X, best.Y) && s.estDamage(u, best) > 2 {
		s.Attack(u, best)
		return
	}
	// 3. 移到「能攻擊到 best 的最近可達格」,再打
	// 2026-08-14: 這一步(0x14EF0 判定原地無立即行動後的移動 fallback)已有
	// disassembly-confirmed 的原生版本(0x14121 blocked-cell 搜索 → 0x13E9C
	// 最近相反陣營單位 → 0x13FD4 原地回復),見 native_ai_movement_fallback.go。
	// 只要這個單位有完整 raw provenance 就優先用原生版；缺資料的單位(如
	// 手動建構的測試 fixture 或舊資產)保留原本的最近可達格近似,不 regress。
	_, nativeOK := s.ApplyNativeAIMovementFallback(u)
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode1MovementFallback(u)
	}
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode2MovementFallback(u)
	}
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode3MovementFallback(u)
	}
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode4MovementFallback(u)
	}
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode5MovementFallback(u)
	}
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode7MovementFallback(u)
	}
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode8MovementFallback(u)
	}
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode9MovementFallback(u)
	}
	if !nativeOK {
		_, nativeOK = s.ApplyNativeAIMode10MovementFallback(u)
	}
	if !nativeOK {
		var dstX, dstY = u.X, u.Y
		bestD := manhattan(u.X, u.Y, best.X, best.Y)
		for _, c := range sortedReachCells(s.Reachable(u)) {
			if s.UnitAt(c.X, c.Y) != nil {
				continue
			}
			d := manhattan(c.X, c.Y, best.X, best.Y)
			if d < bestD {
				bestD = d
				dstX, dstY = c.X, c.Y
			}
		}
		u.SetMapPlacement(dstX, dstY, u.Dir)
	}
	if !nativeAttackOK && best != moveTarget && s.InAttackRange(u, best.X, best.Y) {
		s.Attack(u, best)
	}
	u.Acted = true
}

// AITurn 讓所有非玩家、已登場、未行動的單位(敵 + 友軍 NPC)各行動一次。
func (s *State) AITurn() {
	for _, u := range s.Units {
		if !u.OnField || !u.Alive() || u.Camp == Own || u.Acted || u.Paralyzed {
			continue
		}
		s.aiActUnit(u)
		u.Acted = true
	}
}

// Result 勝負判定。回傳 "win"/"lose"/""。
// 預設規則(可被 scenario 覆寫):敵全滅(且無待命援軍)→ win;
// 任一指定要保護的單位死亡 → lose。
//
// protect 可傳 0..N 個具名單位(空字串一律跳過,不計入判定)。呼叫端(main.go
// checkResult)組合「索爾(通用預設,每章皆判定)」+ 章節額外護衛清單(doc28 §2,
// 例如 ch10 需同時保護「索菲亞」與「卡納恩三世」)一起傳入——這是聯集
// (OR:任一人死即敗),不是用某個名字取代索爾檢查(2026-08-30 前的舊行為是
// 「有 protect 值就只查那一個名字」,會漏掉索爾死亡判定,已修正)。
func (s *State) Result(protect ...string) string {
	for _, name := range protect {
		if name == "" {
			continue
		}
		alive := false
		for _, u := range s.Units {
			if u.Name == name && u.Alive() {
				alive = true
				break
			}
		}
		if !alive {
			return "lose"
		}
	}
	if s.AliveCount(Enemy) == 0 && s.PendingCount(Enemy) == 0 {
		return "win"
	}
	return ""
}

// AIPlan 一個 AI 單位的行動計畫(決策與執行分離,供引擎逐單位播放移動動畫後才結算)。
type AIPlan struct {
	U       *Unit
	Path    []Cell // 含起點;len>=2 = 要移動(引擎播行走動畫)
	Target  *Unit  // 到位後攻擊目標(nil = 僅移動/待機)
	SpellID int    // 原版 spell command 的資料欄位；-1 表示本計畫不施法
	// Destination is the exact record+3 cell 0x1598a scoring chose for
	// SpellID (NativeAISpellCandidate.X/Y, i.e. spell.PositiveWinner.X/Y in
	// nativeAIThreeScorePlan) -- ground truth, not a reconstruction. Threaded
	// straight to NativeCommandEffectTargets by executeNativeCommandTarget so
	// execution doesn't have to rediscover a destination that scoring already
	// computed and validated. nil when SpellID<0, or for plans not sourced
	// from the native spell-scoring path (see #115 in
	// 58-remake-live-verification-log.md for why this exists: a target only
	// reachable via a SelectionMode-internal intermediate cell -- not
	// directly within SelectionMode of actor -- has no way to have that
	// intermediate cell reconstructed correctly from confirmed alone when
	// more than one such cell could work).
	Destination *Cell
	// ItemID/ItemSlot select the AI's native item command (see
	// nativeAIThreeScorePlan/ApplyNativeAIItemCommand), 2026-08-15. ItemID
	// -1 means this plan does not use an item; ItemSlot (the raw inventory
	// slot, 0..7) is only meaningful when ItemID>=0.
	ItemID, ItemSlot int
	// NativeScoredCommands preserves raw command indices that passed the
	// verified command-mask/+0x27/MP gates at 0x1598a. It is evidence only: planner code
	// must still resolve target, score, presentation, and execution separately.
	NativeScoredCommands []int
	// NativeSourced is true when ScoreNativeAI14237 (the disassembly-
	// confirmed native physical-attack composer) produced Path/Target,
	// rather than the aiTargets/estDamage normalized approximation below.
	// Debug/verification only -- gameplay code must not branch on it.
	NativeSourced bool
}

func (s *State) nativeAIPlanScoredCommands(u *Unit) []int {
	if s == nil || len(s.NativeCommandBook) != NativeCommandRecordCount {
		return nil
	}
	return NativeAvailableAIScoredCommandIDs(u, s.NativeCommandBook)
}

// AIAvailableSpells mirrors the data portion of the native AI command scan:
// inventory commands are translated through State.AICommandSpell and then
// resolved against the injected EXE SpellBook. It deliberately does not pick
// a target or score a spell; those rules belong to the later 0x149f8/0x15b77
// decision layer.
func (s *State) AIAvailableSpells(u *Unit) []Spell {
	if s == nil || u == nil || len(s.AICommandSpell) == 0 || len(s.SpellBook) == 0 {
		return nil
	}
	byID := make(map[int]Spell, len(s.SpellBook))
	for _, spell := range s.SpellBook {
		byID[spell.ID] = spell
	}
	seen := make(map[int]bool)
	out := make([]Spell, 0)
	for _, itemID := range u.Inventory {
		spellID, ok := s.AICommandSpell[itemID]
		if !ok || seen[spellID] {
			continue
		}
		spell, ok := byID[spellID]
		if !ok {
			continue
		}
		seen[spellID] = true
		out = append(out, spell)
	}
	return out
}

// AISpellCandidates mirrors the family split visible in 0x15B77. It returns
// candidates in canonical runtime order only; the native score/priority layer
// is intentionally separate and not inferred here.
func (s *State) AISpellCandidates(caster *Unit, spell Spell) []*Unit {
	if s == nil || caster == nil {
		return nil
	}
	family := ""
	switch spell.ID {
	case 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12:
		family = "attack"
	case 13, 14, 15, 16:
		family = "heal"
	case 17, 18, 19:
		family = "buff"
	case 20, 21:
		family = "cure"
	case 22, 26, 27:
		family = "status"
	default:
		return nil
	}
	out := make([]*Unit, 0)
	for _, target := range s.Units {
		if target == nil || !target.OnField || !target.Alive() {
			continue
		}
		sameCamp := target.Camp == caster.Camp
		switch family {
		case "attack":
			if !sameCamp {
				out = append(out, target)
			}
		case "heal":
			if sameCamp && target.HP < target.MaxHP {
				out = append(out, target)
			}
		case "buff":
			if sameCamp {
				out = append(out, target)
			}
		case "cure":
			if sameCamp && ((spell.ID == 20 && target.Poisoned) || (spell.ID == 21 && target.Paralyzed)) {
				out = append(out, target)
			}
		case "status":
			if !sameCamp {
				out = append(out, target)
			}
		}
	}
	return out
}

// NextAIPlan 找下一個未行動的 AI 單位並產生重製端近似計畫
// （不執行、不設 Acted）；它不是原版 0x14237/0x1548e 的替代實作——
// **2026-08-14**:native-accurate 的完整 0x14237 composer(`ScoreNativeAI14237`,
// 見 native_ai_14237.go/native_ai_14237_apply.go 的 `nativeAI14237Plan`)
// 現在優先於下面的 `aiTargets`/`estDamage` normalized 近似:單位有完整 raw
// provenance(裝備/地形/移動成本資料)時直接採用 native 決策,資料不全時
// (ok=false)完全退回既有邏輯,不 regress。這是本函式(不是已無人呼叫的
// `aiActUnit`)才是真正驅動 cmd/fd2 敵方回合演出的路徑,見 main.go 的
// aiStep()/NextAIPlan() 呼叫鏈。
//
// **2026-08-15**:改呼叫 `nativeAIThreeScorePlan`(見
// native_ai_three_score_plan.go),它重現 0x14EF0 完整的三管線決策(物理
// 0x14237 + 法術 0x1598A + 道具 0x1567E + `SelectNativeAIThreeScoreWinner`
// 的勝出者判定),取代只跑物理管線的 `nativeAI14237Plan` 直接呼叫——後者仍
// 存在,被新函式內部呼叫。ok=true/plan=nil 現在代表「三個管線都判定不值得
// 行動」,語意涵蓋原本「物理沒有值得打的目標」的情況,下面的 fallback 分支
// 不需變動。
func (s *State) NextAIPlan() *AIPlan {
	for _, u := range s.Units {
		if !u.OnField || !u.Alive() || u.Camp == Own || u.Acted || u.Paralyzed {
			continue
		}
		nativePlan, nativeOK := s.nativeAIThreeScorePlan(u)
		if nativeOK && nativePlan != nil {
			return nativePlan
		}
		// nativeOK && nativePlan==nil: native 已權威判定原地/可達範圍內沒有值得打
		// 的物理攻擊,下面只借 aiTargets 找移動用的 moveTarget,不採用它的攻擊判斷
		// (best/estDamage),避免 normalized 近似在 native 判過「不值得打」後又打。
		best, moveTarget := s.aiTargets(u)
		if moveTarget == nil {
			return &AIPlan{U: u, SpellID: -1, ItemID: -1, NativeScoredCommands: s.nativeAIPlanScoredCommands(u)}
		}
		if nativeOK || best == nil {
			return &AIPlan{U: u, Path: s.aiApproachPath(u, moveTarget), SpellID: -1, ItemID: -1, NativeScoredCommands: s.nativeAIPlanScoredCommands(u)}
		}
		if s.InAttackRange(u, best.X, best.Y) {
			return &AIPlan{U: u, Target: best, SpellID: -1, ItemID: -1, NativeScoredCommands: s.nativeAIPlanScoredCommands(u)}
		}
		dstX, dstY := u.X, u.Y
		bestD := manhattan(u.X, u.Y, best.X, best.Y)
		for _, c := range sortedReachCells(s.Reachable(u)) {
			if s.UnitAt(c.X, c.Y) != nil {
				continue
			}
			d := manhattan(c.X, c.Y, best.X, best.Y)
			if d < bestD {
				bestD = d
				dstX, dstY = c.X, c.Y
			}
		}
		p := &AIPlan{U: u, Path: s.Path(u, dstX, dstY), SpellID: -1, ItemID: -1, NativeScoredCommands: s.nativeAIPlanScoredCommands(u)}
		// 到位後若可攻擊 best,帶上目標(引擎走完動畫再結算)
		du, dv := dstX-best.X, dstY-best.Y
		if du < 0 {
			du = -du
		}
		if dv < 0 {
			dv = -dv
		}
		if du+dv == 1 {
			p.Target = best
		}
		return p
	}
	return nil
}
