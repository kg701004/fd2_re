package battle

import "fmt"

// RemoveNativeInventorySlot reproduces IDA's 0x1b8e7(unit, slot): the eight
// raw two-byte cells begin at record+0x0a.  It shifts later cells left with
// memmove semantics, then writes 0x80 to the final cell's flag byte.  Item
// bytes remain opaque, including the stale final-cell byte left by native.
func RemoveNativeInventorySlot(records []byte, unitIndex, slot int) error {
	base := unitIndex * nativeRecordSize
	if unitIndex < 0 || base < 0 || base+0x1a > len(records) {
		return recordBoundsError(unitIndex)
	}
	if slot < 0 || slot >= 8 {
		return fmt.Errorf("native inventory slot %d is out of bounds", slot)
	}
	start := base + 0x0a + slot*2
	copy(records[start:start+2*(7-slot)], records[start+2:start+2+2*(7-slot)])
	records[base+0x18] = 0x80
	return nil
}
