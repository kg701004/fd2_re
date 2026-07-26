package battle

import "fmt"

// NativeInventoryOccupiedCount reproduces 0x1b8a6: eight two-byte inventory
// cells begin at record+0x0a, and the native count increments when a cell's
// flag byte bit7 is clear. In the surrounding ABI this is the occupied/raw
// prefix length consumed by 0x31860/0x1b722; bit7 set is the reserved empty
// state used by 0x1bb8c. Item bytes and higher-level item meaning stay opaque.
func NativeInventoryOccupiedCount(records []byte, unitIndex int) (int, error) {
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
