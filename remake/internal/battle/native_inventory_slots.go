package battle

import "fmt"

// NativeInventoryFreeSlotCount reproduces 0x1b8a6: eight two-byte inventory
// cells begin at record+0x0a, and a cell is available when its flag byte's
// bit7 is clear. The item byte and higher-level item meaning stay opaque.
func NativeInventoryFreeSlotCount(records []byte, unitIndex int) (int, error) {
	base := unitIndex * nativeRecordSize
	if unitIndex < 0 || base < 0 || base+0x1a > len(records) {
		return 0, fmt.Errorf("native inventory record %d is out of bounds", unitIndex)
	}
	free := 0
	for slot := 0; slot < 8; slot++ {
		if records[base+0x0a+slot*2]&0x80 == 0 {
			free++
		}
	}
	return free, nil
}
