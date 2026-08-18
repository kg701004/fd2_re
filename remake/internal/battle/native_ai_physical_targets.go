package battle

import "fmt"

// nativeAI39A2CTargetCode reproduces the 0/1/2/3 raw target-code match used
// throughout this session (0x147d5/0x149b0/0x39a2c all share it): 0 requires
// record+6==0, 1 requires !=0, 2 requires ==1, 3 requires ==2.
func nativeAI39A2CTargetCode(recordByte6 byte, code int) bool {
	switch code {
	case 0:
		return recordByte6 == 0
	case 1:
		return recordByte6 != 0
	case 2:
		return recordByte6 == 1
	case 3:
		return recordByte6 == 2
	default:
		return false
	}
}

func nativeAbsInt(v int) int {
	if v < 0 {
		return -v
	}
	return v
}

// NativeAIPhysicalAttackTargets reproduces 0x39a2c: 0x14237's own target-index
// array builder for one candidate destination cell (disassembly-confirmed
// 2026-08-14, docs/knowledge-base/11-enemy-ai.md's "0x14237 composer" section).
// Unlike the generic command-family target field (0x14818,
// NativeCommandTargetFieldBytes), 0x39a2c's own geometry is a plain Manhattan
// distance from the destination cell -- no movement-cost/reachability
// involved, matching a melee/ranged weapon's straight-line reach rather than
// a spell's pathing-constrained area. rangeTiles is the equipped weapon's
// item row +0xc (already read as part of resolving 0x1DEBE's sibling data --
// see native_ai_1debe_adjacency.go); targetCode is 1 if the acting selector
// is 0, else 0 -- i.e. "the opposing group" in the same raw sense used
// throughout this package (nativeAIOppositeSelectorGroup).
//
// Returns target unit indices in roster order (0x39a2c's own scan order),
// active units only, whose cell is within rangeTiles and whose record+6
// matches targetCode.
func NativeAIPhysicalAttackTargets(
	w, h int,
	records []byte,
	count int,
	destX, destY, rangeTiles, targetCode int,
) ([]byte, error) {
	if w <= 0 || h <= 0 || count < 0 || count > 0x100 || len(records) != count*nativeRecordSize {
		return nil, fmt.Errorf("native AI 0x39a2c inputs are malformed")
	}
	if destX < 0 || destY < 0 || destX >= w || destY >= h {
		return nil, fmt.Errorf("native AI 0x39a2c destination is outside the grid")
	}
	if rangeTiles < 0 {
		return nil, fmt.Errorf("native AI 0x39a2c range must be non-negative")
	}
	targets := make([]byte, 0)
	for i := 0; i < count; i++ {
		record := records[i*nativeRecordSize:]
		if record[5]&1 != 0 {
			continue
		}
		x, y := int(record[0]), int(record[1])
		if x < 0 || y < 0 || x >= w || y >= h {
			return nil, fmt.Errorf("native AI 0x39a2c unit %d is outside the grid", i)
		}
		if nativeAbsInt(x-destX)+nativeAbsInt(y-destY) >= rangeTiles {
			continue
		}
		if !nativeAI39A2CTargetCode(record[6], targetCode) {
			continue
		}
		targets = append(targets, byte(i))
	}
	return targets, nil
}
