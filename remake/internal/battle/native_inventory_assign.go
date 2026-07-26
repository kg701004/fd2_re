package battle

import "fmt"

func recordBoundsError(index int) error {
	return fmt.Errorf("native inventory record %d is out of bounds", index)
}

// AssignNativeReservedItem reproduces 0x1bb8c(unit,item): it scans eight
// cells at record+0x0a, consumes the first cell whose flag byte has bit7 set,
// clears that flag, and writes the caller-supplied item byte. The returned
// bool is the native 1/-1 success result.
func AssignNativeReservedItem(records []byte, unitIndex int, itemID byte) (bool, error) {
	base := unitIndex * nativeRecordSize
	if unitIndex < 0 || base < 0 || base+0x1a > len(records) {
		return false, recordBoundsError(unitIndex)
	}
	for slot := 0; slot < 8; slot++ {
		offset := base + 0x0a + slot*2
		if records[offset]&0x80 == 0 {
			continue
		}
		records[offset] = 0
		records[offset+1] = itemID
		return true, nil
	}
	return false, nil
}
