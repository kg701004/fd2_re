package battle

// MoveType selects which column of doc02 §3.1's terrain-cost table a unit
// pays. MoveWalk is the zero value so every Unit literal or JSON record that
// predates this field keeps its exact old behavior with no migration needed.
type MoveType int

const (
	MoveWalk MoveType = iota
	MoveCavalry
	MoveFly
)

// Reachable 回傳單位可移動到的格(flood-fill BFS,MV 步內,避開其他單位與邊界)。
// 成本依 MoveCostFor 查地形表(worklist 第 8 輪接上;無資料時退回全平地=1)。
func (s *State) Reachable(u *Unit) map[Cell]bool {
	res := map[Cell]bool{{u.X, u.Y}: true}
	cost := map[Cell]int{{u.X, u.Y}: 0}
	q := []Cell{{u.X, u.Y}}
	for len(q) > 0 {
		c := q[0]
		q = q[1:]
		if cost[c] >= u.MV {
			continue
		}
		for _, d := range [][2]int{{0, -1}, {0, 1}, {-1, 0}, {1, 0}} {
			nx, ny := c.X+d[0], c.Y+d[1]
			if nx < 0 || ny < 0 || nx >= s.W || ny >= s.H {
				continue
			}
			nc := Cell{nx, ny}
			if _, seen := cost[nc]; seen {
				continue
			}
			if o := s.UnitAt(nx, ny); o != nil && o != u { // 他人擋路(同陣營也擋,簡化)
				continue
			}
			nco := cost[c] + s.MoveCostFor(u, nx, ny)
			if nco <= u.MV {
				cost[nc] = nco
				res[nc] = true
				q = append(q, nc)
			}
		}
	}
	return res
}

// MoveCost 進入該格的移動成本(步行基準值)。查 s.Cost(Load 從 map.json "cost" 陣列接上,
// doc01 §5 地形控制表換算;worklist 第 8 輪「地形屬性接線」);無地形資料(s.Cost==nil,
// 如舊測試直接手寫 State{})或座標越界一律回 1(平地)。不可通行地形回一個遠大於任何 MV
// 的值(export_engine_assets.py 的 BLOCKED_COST=99),Reachable/Path 的 `nco <= u.MV`
// 判斷天然把它篩掉,不需要另外特判「牆」。這是「步行」這一欄的值(doc02 §3.1 步行/騎兵/
// 飛行三欄裡,步行對森林=1、平地=1 剛好相同,map.json 匯出時只烘焙了一份成本,所以這個
// 陣列本身其實就是步行基準——MoveCostFor 會在需要時,用 NativeTerrainMoveCodes 換算出
// 其他移動類型的差異)。
func (s *State) MoveCost(x, y int) int {
	if s.Cost == nil || x < 0 || y < 0 || x >= s.W || y >= s.H {
		return 1
	}
	return s.Cost[y*s.W+x]
}

// nativeTerrainKind classifies a unit's terrain (plain/forest/swamp) from the
// same FDSHAP control byte already proven for the AP/DP HUD bonus (see
// indexedmap.NativeMapHUDTerrainAPDP: 0=plain, 1/5=neutral, 2/3=forest,
// 4=swamp). Returns ok=false for values outside 0..5 (unknown/unavailable).
func nativeTerrainKind(controlByte byte) (forest, swamp, ok bool) {
	switch controlByte {
	case 0, 1, 5:
		return false, false, true
	case 2, 3:
		return true, false, true
	case 4:
		return false, true, true
	default:
		return false, false, false
	}
}

// MoveCostFor is MoveCost adjusted for the unit's real per-class terrain
// cost (see nativeMoveCost). Blocked base tiles (MoveCost >= 99 -- walls,
// map edges) stay blocked for every unit regardless of class: that's a map
// structure fact, not a per-class distinction. When the native 29-row table
// or terrain codes aren't loaded (older test fixtures, hand-built State{}
// literals), falls back to the earlier doc02 §3.1 walk/cavalry/fly
// approximation keyed on u.MoveType, which stays a strict no-op for every
// MoveWalk unit -- the only kind any shipped roster currently sets.
func (s *State) MoveCostFor(u *Unit, x, y int) int {
	base := s.MoveCost(x, y)
	if u == nil || base >= 99 {
		return base
	}
	if native, ok := s.nativeMoveCost(u, x, y); ok {
		return native
	}
	if u.MoveType == MoveWalk {
		return base
	}
	if u.MoveType == MoveFly {
		return 1 // 飛行忽略地形,永遠 1(doc02 §3.1)
	}
	if len(s.NativeTerrainMoveCodes) != s.W*s.H || x < 0 || y < 0 || x >= s.W || y >= s.H {
		return base
	}
	forest, swamp, ok := nativeTerrainKind(s.NativeTerrainMoveCodes[y*s.W+x])
	if !ok {
		return base
	}
	switch {
	case forest:
		return 2 // 步行 1 → 騎兵 2
	case swamp:
		return 3 // 步行 2 → 騎兵 3
	default:
		return base // 平地/中性地形:騎兵跟步行相同
	}
}

// nativeMovementRow19Predicate implements native 0x1f183, disassembly-confirmed
// 2026-08-14 (Ghidra decompile of the "新版" reference FD2.EXE):
//
//	record := unitArrayBase + actorIndex*0x50
//	if record+0x7 == 0x1c: return false
//	if record+0x20 == 0x13: return true   // class ID 0x13
//	if record+0x1f in {4, 5}: return true // race
//	return false
//
// record+0x1f/+0x20 are already modeled as NativeRecordRace/ClassID. The
// record+7 gate byte is a genuinely new field this predicate is the first
// known consumer of -- no export pipeline populates it yet for any map's
// units.json, so it is intentionally omitted here (never guessed) rather
// than modeled as an always-false field. This mirrors how NativeRecordByte8
// elsewhere in this file is treated as "not yet known" rather than "0" when
// absent: omitting the gate only risks applying the row-19 override to a few
// units that the original would have suppressed via record+7==0x1c, which is
// strictly narrower than the prior behavior of never applying it at all.
func nativeMovementRow19Predicate(u *Unit) bool {
	if u.ClassID == 0x13 {
		return true
	}
	if u.HasNativeRecordRace && (u.NativeRecordRace == 4 || u.NativeRecordRace == 5) {
		return true
	}
	return false
}

// nativeMoveCost implements the confirmed native 0x4e555 per-class terrain
// cost lookup. The full selector derivation is now disassembly-confirmed at
// its actual call site 0x14b78 (Ghidra decompile of the "新版" reference EXE,
// 2026-08-14, cross-checked against docs/knowledge-base/11-enemy-ai.md):
//
//	selector = record+0x20               // class, the default
//	if nativeMovementRow19Predicate(actor): selector = 0x13  // row 19
//	if record+8 == 0x1c: selector = 1                        // row 1, checked
//	                                                          // LAST -- wins
//	                                                          // over row 19
//	                                                          // if both hold
//
// (0x14b78: `MOVZX ESI,[EBX+0x20]` default: `CALL 0x1f183; TEST EAX,EAX; JZ
// skip; MOV ESI,0x13` row-19 override; `MOVZX EAX,[EBX+8]; CMP EAX,0x1c; JNZ
// skip; MOV ESI,0x1` row-1 override applied after, unconditionally.) Row
// 20-and-up values mark the class as unable to enter that terrain at all
// (NativeRelocationDestinationAllowed treats exactly 20 as its "blocked"
// test); this returns the same 99 blocked-tile sentinel MoveCost uses so
// Reachable/Path's existing `nco <= u.MV` cutoff excludes it without a
// separate special case.
// nativeMovementCostRowSelector computes the same selector as the inline
// comment above documents (class default, row19 predicate override, then
// record+8==0x1c row1 override applied last). Factored out so other callers
// (e.g. the AI movement fallback) can fetch a unit's cost row without
// duplicating this selection logic.
func nativeMovementCostRowSelector(u *Unit) int {
	selector := u.ClassID
	if nativeMovementRow19Predicate(u) {
		selector = 0x13
	}
	if u.HasNativeRecordByte8 && u.NativeRecordByte8 == 0x1c {
		selector = 1
	}
	return selector
}

// nativeMovementCostRowFor returns the raw 20-byte cost row for u, or
// (nil, false) if native movement data isn't loaded or the selector is out
// of range.
func (s *State) nativeMovementCostRowFor(u *Unit) ([]byte, bool) {
	if len(s.NativeMovementCostRows) != NativeMovementCostRowCount {
		return nil, false
	}
	selector := nativeMovementCostRowSelector(u)
	if selector < 0 || selector >= len(s.NativeMovementCostRows) {
		return nil, false
	}
	row := s.NativeMovementCostRows[selector]
	if len(row) != NativeMovementCostRowSize {
		return nil, false
	}
	return row, true
}

func (s *State) nativeMoveCost(u *Unit, x, y int) (int, bool) {
	if len(s.NativeMovementCostRows) != NativeMovementCostRowCount ||
		len(s.NativeTerrainMoveCodes) != s.W*s.H ||
		x < 0 || y < 0 || x >= s.W || y >= s.H {
		return 0, false
	}
	selector := nativeMovementCostRowSelector(u)
	if selector < 0 || selector >= len(s.NativeMovementCostRows) {
		return 0, false
	}
	row := s.NativeMovementCostRows[selector]
	terrainIndex := int(s.NativeTerrainMoveCodes[y*s.W+x])
	if len(row) != NativeMovementCostRowSize || terrainIndex < 0 || terrainIndex >= len(row) {
		return 0, false
	}
	if cost := int(row[terrainIndex]); cost < 20 {
		return cost, true
	}
	return 99, true
}

// InAttackRange 目標是否在攻擊範圍(曼哈頓距離落在 [AtkMin,AtkMax] 內;doc32 依武器
// type 決定,如騎士槍type3=[1,2]。AtkMin/AtkMax 未設(0)一律視為預設 1,等同舊版
// 「只查相鄰 4 格」行為不變)。
func (s *State) InAttackRange(u *Unit, tx, ty int) bool {
	dx, dy := tx-u.X, ty-u.Y
	if dx < 0 {
		dx = -dx
	}
	if dy < 0 {
		dy = -dy
	}
	d := dx + dy
	min, max := u.AtkMin, u.AtkMax
	if min == 0 {
		min = 1
	}
	if max == 0 {
		max = 1
	}
	return d >= min && d <= max
}

// Path 回傳 u 走到 (tx,ty) 的逐格路徑(含起點;BFS,同 Reachable 規則)。不可達回 nil。
func (s *State) Path(u *Unit, tx, ty int) []Cell {
	start := Cell{X: u.X, Y: u.Y}
	goal := Cell{X: tx, Y: ty}
	if start == goal {
		return []Cell{start}
	}
	cost := map[Cell]int{start: 0}
	par := map[Cell]Cell{}
	q := []Cell{start}
	for len(q) > 0 {
		c := q[0]
		q = q[1:]
		if cost[c] >= u.MV {
			continue
		}
		for _, d := range [][2]int{{0, -1}, {0, 1}, {-1, 0}, {1, 0}} {
			nx, ny := c.X+d[0], c.Y+d[1]
			if nx < 0 || ny < 0 || nx >= s.W || ny >= s.H {
				continue
			}
			nc := Cell{X: nx, Y: ny}
			if _, seen := cost[nc]; seen {
				continue
			}
			if o := s.UnitAt(nx, ny); o != nil && o != u {
				continue
			}
			nco := cost[c] + s.MoveCostFor(u, nx, ny)
			if nco <= u.MV {
				cost[nc] = nco
				par[nc] = c
				q = append(q, nc)
			}
		}
	}
	if _, ok := cost[goal]; !ok {
		return nil
	}
	path := []Cell{goal}
	for p := goal; p != start; {
		p = par[p]
		path = append([]Cell{p}, path...)
	}
	return path
}
