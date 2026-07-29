package battle

import "fmt"

const (
	NativePathDown byte = iota
	NativePathLeft
	NativePathUp
	NativePathRight
)

// SelectNativeMovementDestination mirrors 0x14b78's 0x14dc5..0x14e56
// reachable-cell ranking. It first minimizes Manhattan distance to intended,
// then minimizes the absolute X/Y distance imbalance. Exact ties preserve the
// caller's existing candidate order.
func SelectNativeMovementDestination(candidates []Cell, intended Cell) (Cell, bool) {
	best := intended
	bestDistance, bestImbalance := 0xff, 0xff
	found := false
	for _, candidate := range candidates {
		distance, imbalance := nativeMovementDestinationMetrics(candidate, intended)
		if distance < bestDistance || distance == bestDistance && imbalance < bestImbalance {
			best = candidate
			bestDistance, bestImbalance = distance, imbalance
			found = true
		}
	}
	return best, found
}

// NativePathBlockedCoordinate reproduces the mode-2 use of 0x4e1a6 in
// 0x14121. Unlike modes 0/1, mode 2 enters 0x40 cells, records their
// coordinates, and keeps traversing. Every later accepted blocked cell
// overwrites the prior result, so the answer follows the original DFS order
// rather than a nearest-distance rule.
func NativePathBlockedCoordinate(
	w, h int,
	start Cell,
	initialBudget int,
	flags, terrainMoveCodes, costRow []byte,
) (Cell, bool, error) {
	if w <= 0 || h <= 0 ||
		start.X < 0 || start.Y < 0 || start.X >= w || start.Y >= h ||
		initialBudget < 0 || initialBudget > 0xff ||
		len(flags) != w*h || len(terrainMoveCodes) != w*h ||
		len(costRow) != NativeMovementCostRowSize {
		return Cell{}, false, fmt.Errorf("native blocked-coordinate path inputs are malformed")
	}
	for cell, code := range terrainMoveCodes {
		if int(code) >= len(costRow) {
			return Cell{}, false, fmt.Errorf("native blocked-coordinate terrain code %d at cell %d is out of bounds", code, cell)
		}
	}
	budgets := make([]byte, w*h)
	for index := range budgets {
		budgets[index] = 0xff
	}
	budgets[start.Y*w+start.X] = byte(initialBudget)
	var result Cell
	found := false
	var walk func(Cell, byte)
	walk = func(cell Cell, budget byte) {
		for _, neighbour := range nativePathNeighbours {
			next := Cell{X: cell.X + neighbour.dx, Y: cell.Y + neighbour.dy}
			if next.X < 0 || next.Y < 0 || next.X >= w || next.Y >= h {
				continue
			}
			index := next.Y*w + next.X
			cost := costRow[terrainMoveCodes[index]]
			if cost > budget {
				continue
			}
			nextBudget := budget - cost
			if int8(nextBudget) <= int8(budgets[index]) {
				continue
			}
			budgets[index] = nextBudget
			if flags[index]&NativeCommandGridBlocked != 0 {
				result, found = next, true
			}
			walk(next, nextBudget)
		}
	}
	walk(start, byte(initialBudget))
	return result, found, nil
}

func nativeMovementDestinationMetrics(candidate, intended Cell) (distance, imbalance int) {
	dx := absInt(candidate.X - intended.X)
	dy := absInt(candidate.Y - intended.Y)
	return dx + dy, absInt(dx - dy)
}

// SelectNativeNearestOppositeCoordinate mirrors 0x13e9c's final movement
// fallback. selector remains raw: zero scans records with record+6 != 0;
// nonzero scans record+6 == 0. The routine does not apply active/dead gates
// and retains the first runtime record on an exact Manhattan-distance tie.
func SelectNativeNearestOppositeCoordinate(
	records []byte,
	count, actor, selector int,
) (Cell, bool, error) {
	if count < 0 || count > len(records)/nativeRecordSize || actor < 0 || actor >= count {
		return Cell{}, false, fmt.Errorf("native nearest-coordinate roster/actor is malformed")
	}
	actorRecord := records[actor*nativeRecordSize:]
	origin := Cell{X: int(actorRecord[0]), Y: int(actorRecord[1])}
	bestDistance := 0xffff
	var best Cell
	found := false
	for unit := 0; unit < count; unit++ {
		record := records[unit*nativeRecordSize:]
		if !nativeAIOppositeSelectorGroup(record[6], selector) {
			continue
		}
		candidate := Cell{X: int(record[0]), Y: int(record[1])}
		distance := absInt(origin.X-candidate.X) + absInt(origin.Y-candidate.Y)
		if distance >= bestDistance {
			continue
		}
		best, bestDistance, found = candidate, distance, true
	}
	return best, found, nil
}

// NativePathDirections reproduces 0x4e1a6 modes 0 and 1. It returns the
// original direction bytes consumed by 0x13488. Mode 0 keeps only a strictly
// better remaining budget per cell. Mode 1 may replace an equal-budget visit
// when the current route has more direction runs, matching 0x4e35b..0x4e373.
//
// flags is FDFIELD entry+2 and terrainMoveCodes is the already validated
// FDSHAP record+1 projection used by the original cost-row lookup.
func NativePathDirections(
	w, h int,
	start, destination Cell,
	initialBudget, mode int,
	flags, terrainMoveCodes, costRow []byte,
) ([]byte, bool, error) {
	if w <= 0 || h <= 0 ||
		start.X < 0 || start.Y < 0 || start.X >= w || start.Y >= h ||
		destination.X < 0 || destination.Y < 0 || destination.X >= w || destination.Y >= h ||
		initialBudget < 0 || initialBudget > 0xff ||
		(mode != 0 && mode != 1) ||
		len(flags) != w*h || len(terrainMoveCodes) != w*h ||
		len(costRow) != NativeMovementCostRowSize {
		return nil, false, fmt.Errorf("native path inputs are malformed")
	}
	for cell, code := range terrainMoveCodes {
		if int(code) >= len(costRow) {
			return nil, false, fmt.Errorf("native path terrain code %d at cell %d is out of bounds", code, cell)
		}
	}

	search := nativePathSearch{
		w:                w,
		h:                h,
		destination:      destination,
		mode:             mode,
		flags:            flags,
		terrainMoveCodes: terrainMoveCodes,
		costRow:          costRow,
		budgets:          make([]byte, w*h),
		runMetrics:       make([]byte, w*h),
		bestLength:       0xff,
	}
	for index := range search.budgets {
		search.budgets[index] = 0xff
	}
	search.budgets[start.Y*w+start.X] = byte(initialBudget)
	search.considerDestination(start)
	search.walk(start, byte(initialBudget))
	if search.bestLength == 0xff {
		return nil, false, nil
	}
	return append([]byte(nil), search.bestPath...), true, nil
}

type nativePathSearch struct {
	w, h             int
	destination      Cell
	mode             int
	flags            []byte
	terrainMoveCodes []byte
	costRow          []byte
	budgets          []byte
	runMetrics       []byte
	path             []byte
	bestPath         []byte
	bestLength       int
}

var nativePathNeighbours = []struct {
	dx, dy int
	code   byte
}{
	{dx: 1, dy: 0, code: NativePathRight},
	{dx: -1, dy: 0, code: NativePathLeft},
	{dx: 0, dy: 1, code: NativePathDown},
	{dx: 0, dy: -1, code: NativePathUp},
}

func (search *nativePathSearch) walk(cell Cell, budget byte) {
	for _, neighbour := range nativePathNeighbours {
		next := Cell{X: cell.X + neighbour.dx, Y: cell.Y + neighbour.dy}
		if next.X < 0 || next.Y < 0 || next.X >= search.w || next.Y >= search.h {
			continue
		}
		index := next.Y*search.w + next.X
		cost := search.costRow[search.terrainMoveCodes[index]]
		if cost > budget {
			continue
		}
		nextBudget := budget - cost
		oldBudget := search.budgets[index]
		search.path = append(search.path, neighbour.code)
		runMetric := nativePathRunMetric(search.path)
		accept := int8(nextBudget) > int8(oldBudget)
		if int8(nextBudget) == int8(oldBudget) && search.mode == 1 {
			accept = runMetric > search.runMetrics[index]
		}
		if accept {
			// 0x4e37a updates the path-run metadata before testing flags.
			search.runMetrics[index] = runMetric
			if search.flags[index]&NativeCommandGridBlocked == 0 {
				if search.flags[index]&NativeCommandGridZeroBudget != 0 {
					nextBudget = 0
				}
				search.budgets[index] = nextBudget
				search.considerDestination(next)
				search.walk(next, nextBudget)
			}
		}
		search.path = search.path[:len(search.path)-1]
	}
}

func nativePathRunMetric(path []byte) byte {
	if len(path) == 0 {
		return 0
	}
	runs := 1
	for index := 1; index < len(path); index++ {
		if path[index] != path[index-1] {
			runs++
		}
	}
	return byte(runs << 2)
}

func (search *nativePathSearch) considerDestination(cell Cell) {
	if cell != search.destination || len(search.path) > search.bestLength {
		return
	}
	search.bestLength = len(search.path)
	search.bestPath = append(search.bestPath[:0], search.path...)
}
