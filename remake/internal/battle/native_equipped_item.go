package battle

import "fmt"

// NativeEquippedInventorySlot reproduces 0x1b83d(unit,a2). It scans runtime
// cells in order, requires flag bit 0x40, then selects item bytes below 0x80
// when a2==0 and bytes >=0x80 when a2!=0. The return value is the raw runtime
// slot, or -1 for native not-found; no weapon/effect name is inferred.
func NativeEquippedInventorySlot(flags, slots []int, a2 int) (int, error) {
	if len(flags) != nativeInventoryCells || len(slots) != nativeInventoryCells {
		return -1, fmt.Errorf("native equipped item: need %d flags and slots", nativeInventoryCells)
	}
	for slot := 0; slot < nativeInventoryCells; slot++ {
		if flags[slot] < 0 || flags[slot] > 0xff || slots[slot] < 0 || slots[slot] > 0xff {
			return -1, fmt.Errorf("native equipped item: malformed cell %d", slot)
		}
		if flags[slot]&0x40 == 0 {
			continue
		}
		if (a2 == 0 && slots[slot] < 0x80) || (a2 != 0 && slots[slot] >= 0x80) {
			return slot, nil
		}
	}
	return -1, nil
}
