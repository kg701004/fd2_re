package battle

import (
	"encoding/binary"
	"fmt"
)

// ApplyNativeWordDeltaAndRemove reproduces the mutation portion of 0x21082:
// add a signed caller-supplied delta to a raw unit word, then invoke the
// proven 0x1b8e7 inventory-slot removal on the caller's unit/slot. Types
// 8/9/0xa identify offsets +0x37/+0x39/+0x3e as base AP/DP/DX; other callers
// must retain their own evidence boundary. Native renderer/recalculation
// callbacks remain outside this adapter.
func ApplyNativeWordDeltaAndRemove(records []byte, targetUnit, wordOffset int, delta int, removalUnit, removalSlot int) (uint16, error) {
	base := targetUnit * nativeRecordSize
	if targetUnit < 0 || base < 0 || base+nativeRecordSize > len(records) {
		return 0, recordBoundsError(targetUnit)
	}
	if wordOffset < 0 || wordOffset+2 > nativeRecordSize {
		return 0, fmt.Errorf("native word offset %#x is out of bounds", wordOffset)
	}
	removalBase := removalUnit * nativeRecordSize
	if removalUnit < 0 || removalBase < 0 || removalBase+0x1a > len(records) {
		return 0, recordBoundsError(removalUnit)
	}
	if removalSlot < 0 || removalSlot >= 8 {
		return 0, fmt.Errorf("native inventory slot %d is out of bounds", removalSlot)
	}
	offset := base + wordOffset
	value := binary.LittleEndian.Uint16(records[offset : offset+2])
	value += uint16(int16(delta))
	binary.LittleEndian.PutUint16(records[offset:offset+2], value)
	if err := RemoveNativeInventorySlot(records, removalUnit, removalSlot); err != nil {
		return 0, err
	}
	return value, nil
}
