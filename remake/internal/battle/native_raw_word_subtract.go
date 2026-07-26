package battle

import (
	"encoding/binary"
	"fmt"
)

// ApplyNativeRawWordSubtract reproduces the write core used by 0x1cac7:
// subtract a caller-supplied byte-sized value from a selected record word and
// store the low 16 bits. The word offset remains explicit because the native
// caller's field name is not proven by this helper.
func ApplyNativeRawWordSubtract(records []byte, unitIndex, wordOffset, amount int) (uint16, error) {
	if unitIndex < 0 || unitIndex >= len(records)/nativeRecordSize {
		return 0, recordBoundsError(unitIndex)
	}
	if wordOffset < 0 || wordOffset+2 > nativeRecordSize {
		return 0, fmt.Errorf("native word offset %#x is out of bounds", wordOffset)
	}
	if amount < 0 || amount > 0xff {
		return 0, fmt.Errorf("native subtract amount %d is out of byte range", amount)
	}
	record := records[unitIndex*nativeRecordSize:]
	value := binary.LittleEndian.Uint16(record[wordOffset : wordOffset+2])
	updated := value - uint16(amount)
	binary.LittleEndian.PutUint16(record[wordOffset:wordOffset+2], updated)
	return updated, nil
}
