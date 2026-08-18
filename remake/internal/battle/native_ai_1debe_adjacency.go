package battle

import "fmt"

// NativeAI1DEBEAdjacencyGate reproduces 0x1debe(actor,x,y), closed in a prior
// session (docs/knowledge-base/91-worklist.md's
// RE-ITEM-ADJACENCY-GATE-1DEBE entry, cross-referenced in doc11/doc32): the
// gate 0x14237's physical scoring adds via `0x1448A->0x1DEBE` (score +=
// actor word4A - target word48 when this returns true). Three raw
// conditions, all required:
//
//  1. actor is active (record+5 bit0 clear -- the same gate used throughout
//     this package).
//  2. (x,y) is Manhattan-adjacent to the actor's own position (exactly one
//     cell away, not zero and not diagonal-as-two).
//  3. the actor's equipped weapon (0x1b83d(actor,0) -- NativeEquippedInventorySlot
//     with a2==0, the same "item id <0x80" attack precondition already used
//     by the action-overlay adapter) has item row +0x0b <= 1. No weapon
//     found (0x1b83d returns -1) means this condition cannot hold.
//
// Row +0x0b's own game meaning is NOT named (doc32: "不能推出 item +0x0b
// 是所有武器的通用最大射程" -- it is caller-specific geometry, kept raw here
// too).
func NativeAI1DEBEAdjacencyGate(
	records []byte,
	itemRows []byte,
	count, actor, x, y int,
) (bool, error) {
	if count < 0 || count > 0x100 || len(records) != count*nativeRecordSize ||
		actor < 0 || actor >= count {
		return false, fmt.Errorf("native AI 0x1debe roster/actor is malformed")
	}
	if len(itemRows) == 0 || len(itemRows)%NativeItemEffectRowSize != 0 {
		return false, fmt.Errorf("native AI 0x1debe item rows are malformed")
	}
	record := records[actor*nativeRecordSize:]
	if record[5]&1 != 0 {
		return false, nil
	}
	actorX, actorY := int(record[0]), int(record[1])
	dx, dy := actorX-x, actorY-y
	if dx < 0 {
		dx = -dx
	}
	if dy < 0 {
		dy = -dy
	}
	if dx+dy != 1 {
		return false, nil
	}
	flags := make([]int, nativeInventoryCells)
	slots := make([]int, nativeInventoryCells)
	for cell := 0; cell < nativeInventoryCells; cell++ {
		flags[cell] = int(record[nativeInventoryOffset+cell*2])
		slots[cell] = int(record[nativeInventoryOffset+cell*2+1])
	}
	weaponSlot, err := NativeEquippedInventorySlot(flags, slots, 0)
	if err != nil {
		return false, err
	}
	if weaponSlot < 0 {
		return false, nil
	}
	itemID := slots[weaponSlot]
	rowOffset, err := NativeItemEffectRowOffset(itemID)
	if err != nil {
		return false, err
	}
	if rowOffset+0x0c > len(itemRows) {
		return false, fmt.Errorf("native AI 0x1debe item %d row is unavailable", itemID)
	}
	return itemRows[rowOffset+0x0b] <= 1, nil
}
