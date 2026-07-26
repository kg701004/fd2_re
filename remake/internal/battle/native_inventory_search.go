package battle

import "fmt"

// FindNativeInventoryItemInUnit reproduces the raw search used by 0x31860.
// Native inventory cells are ordered as eight two-byte cells at record+0x0a;
// 0x31860 first obtains the occupied/prefix count from 0x1b8a6 and then
// compares only that prefix's item bytes at +0x0b. The flag/item bytes remain
// opaque; this helper does not consume or mutate a cell.
func FindNativeInventoryItemInUnit(records []byte, unitIndex int, item byte) (int, error) {
	base := unitIndex * nativeRecordSize
	if unitIndex < 0 || base < 0 || base+0x1a > len(records) {
		return -1, recordBoundsError(unitIndex)
	}
	count, err := NativeInventoryOccupiedCount(records, unitIndex)
	if err != nil {
		return -1, err
	}
	for slot := 0; slot < count; slot++ {
		if records[base+0x0b+slot*2] == item {
			return slot, nil
		}
	}
	return -1, nil
}

// FindNativeInventoryItem reproduces 0x24b14(item): scan runtime units 0..15
// and return the first matching unit/slot.  A missing item returns (-1,-1),
// matching the native -1 return while preserving the useful raw location for
// the successful editable gate.  The search is read-only and fail-closed.
func FindNativeInventoryItem(records []byte, item byte) (unitIndex, slot int, err error) {
	if len(records) < 16*nativeRecordSize {
		return -1, -1, fmt.Errorf("native inventory search needs 16 records, got %d bytes", len(records))
	}
	for unit := 0; unit < 16; unit++ {
		found, err := FindNativeInventoryItemInUnit(records, unit, item)
		if err != nil {
			return -1, -1, err
		}
		if found >= 0 {
			return unit, found, nil
		}
	}
	return -1, -1, nil
}
