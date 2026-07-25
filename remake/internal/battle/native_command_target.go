package battle

import "fmt"

const (
	// NativeCommandGridBlocked is original grid flag bit 0x40: 0x4e16e
	// refuses to enter this cell during the dist<0x10 flood-fill.
	NativeCommandGridBlocked byte = 0x40
	// NativeCommandGridZeroCost is original grid flag bit 0x80: 0x4e16e
	// clears the step cost after passing the blocked check.
	NativeCommandGridZeroCost byte = 0x80
)

// NativeCommandTargetCells mirrors one 0x14818 geometry invocation before
// roster filtering.  It intentionally accepts the raw fourth argument
// (called mode in the original callsite), rather than declaring it a command
// range: generic 0x1cff0 first calls it with record+3 from the actor, lets the
// cursor confirm a candidate, then calls it again with record+4 from that
// cursor cell to build the effect list.  Callers must select the correct stage.
//
// flags is the original per-cell grid flag byte (+1 in its 4-byte grid entry),
// not the remake map's exported movement cost.  Requiring it avoids silently
// treating a modern approximation as original targeting data.
func NativeCommandTargetCells(w, h int, origin Cell, dist int, flags []byte) (map[Cell]bool, error) {
	if w <= 0 || h <= 0 || origin.X < 0 || origin.Y < 0 || origin.X >= w || origin.Y >= h {
		return nil, fmt.Errorf("invalid native target grid/origin")
	}
	if len(flags) != w*h {
		return nil, fmt.Errorf("native target flags len=%d want %d", len(flags), w*h)
	}
	if dist < 0 {
		return nil, fmt.Errorf("invalid native target dist=%d", dist)
	}
	result := make(map[Cell]bool)
	if dist >= 0x10 { // 0x148c7: cross ignores the grid flags.
		radius := dist - 0x10
		for x := 0; x < w; x++ {
			if absInt(x-origin.X) <= radius {
				result[Cell{X: x, Y: origin.Y}] = true
			}
		}
		for y := 0; y < h; y++ {
			if absInt(y-origin.Y) <= radius {
				result[Cell{X: origin.X, Y: y}] = true
			}
		}
		return result, nil
	}

	// 0x4e040 starts the origin at budget=dist then recursively visits the
	// four cardinal neighbours. Row 0's twenty terrain costs are all one.
	remaining := map[Cell]int{{X: origin.X, Y: origin.Y}: dist}
	queue := []Cell{origin}
	result[origin] = true
	for len(queue) > 0 {
		cell := queue[0]
		queue = queue[1:]
		for _, d := range [][2]int{{1, 0}, {-1, 0}, {0, 1}, {0, -1}} {
			next := Cell{X: cell.X + d[0], Y: cell.Y + d[1]}
			if next.X < 0 || next.Y < 0 || next.X >= w || next.Y >= h {
				continue
			}
			flag := flags[next.Y*w+next.X]
			if flag&NativeCommandGridBlocked != 0 {
				continue
			}
			step := 1
			if flag&NativeCommandGridZeroCost != 0 {
				step = 0
			}
			nextBudget := remaining[cell] - step
			if nextBudget < 0 {
				continue
			}
			if old, seen := remaining[next]; seen && old >= nextBudget {
				continue
			}
			remaining[next] = nextBudget
			result[next] = true
			queue = append(queue, next)
		}
	}
	return result, nil
}

func absInt(n int) int {
	if n < 0 {
		return -n
	}
	return n
}

// NativeCommandTargetMatches is the exact record+6 predicate in 0x14818.
// The native constructor ABI is Enemy=0, Ally=1, Own=2, whereas the Go Camp
// enum is Own=0, Ally=1, Enemy=2.  Use named values here rather than copying
// the native ordinals into the remake model.
func NativeCommandTargetMatches(code int, camp Camp) bool {
	switch code {
	case 0:
		return camp == Enemy
	case 1:
		return camp != Enemy
	case 2:
		return camp != Ally
	case 3:
		return camp == Own
	default:
		return false
	}
}

// NativeCommandTargets applies one recovered 0x14818 invocation and its
// record+6 camp predicate to runtime units.  It is deliberately independent
// of CastArea; for generic commands its origin/mode must be the confirmed
// cursor and record+4 to represent the final effect list.
func NativeCommandTargets(w, h int, origin Cell, dist, targetCode int, flags []byte, units []*Unit) ([]*Unit, error) {
	cells, err := NativeCommandTargetCells(w, h, origin, dist, flags)
	if err != nil {
		return nil, err
	}
	var targets []*Unit
	for _, unit := range units {
		if unit == nil || !unit.OnField || !unit.Alive() || !NativeCommandTargetMatches(targetCode, unit.Camp) {
			continue
		}
		if cells[Cell{X: unit.X, Y: unit.Y}] {
			targets = append(targets, unit)
		}
	}
	return targets, nil
}

// NativeCommandEffectTargets mirrors the generic two-stage 0x1cff0 path.
// The first 0x14818 call originates at actor with record+3; 0x115b6 confirms
// one member of that list; the second call originates at the confirmed unit's
// cell with record+4 and supplies the effect list to 0x2a6bd.  It deliberately
// excludes the command 0x17/0x1e special branches and all presentation.
func NativeCommandEffectTargets(w, h int, actor, confirmed *Unit, selectionMode, effectMode, targetCode int, flags []byte, units []*Unit) ([]*Unit, error) {
	if actor == nil || confirmed == nil || !actor.OnField || !confirmed.OnField {
		return nil, fmt.Errorf("invalid native command actor/confirmed unit")
	}
	selection, err := NativeCommandTargets(w, h, Cell{X: actor.X, Y: actor.Y}, selectionMode, targetCode, flags, units)
	if err != nil {
		return nil, err
	}
	confirmedCandidate := false
	for _, candidate := range selection {
		if candidate == confirmed {
			confirmedCandidate = true
			break
		}
	}
	if !confirmedCandidate {
		return nil, fmt.Errorf("confirmed unit is not a native command candidate")
	}
	return NativeCommandTargets(w, h, Cell{X: confirmed.X, Y: confirmed.Y}, effectMode, targetCode, flags, units)
}
