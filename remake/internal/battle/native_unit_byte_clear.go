package battle

import "fmt"

// NativeUnitByteClearResult is the mutation-only portion of 0x22af6.  The
// caller supplies unit indices and a raw record offset; gameplay meaning of
// the byte and the accumulated value is intentionally not named.
type NativeUnitByteClearResult struct {
	UnitIndex int
	Cleared   bool
	RawValue  int
}

// ClearNativeUnitByte reproduces 0x22af6's per-unit mutation.  For each
// supplied index, a nonzero record[fieldOffset] is cleared and contributes
// 4*effective(record+0x21) to the raw accumulator.  The effective value adds
// 30 when record+0x20 is in (8,25).  Rendering callbacks and global writes are
// deliberately outside this pure adapter.
func ClearNativeUnitByte(records []byte, unitIndices []byte, fieldOffset int) ([]NativeUnitByteClearResult, int, error) {
	if fieldOffset < 0 || fieldOffset >= nativeRecordSize {
		return nil, 0, fmt.Errorf("native unit field offset %#x is out of bounds", fieldOffset)
	}
	results := make([]NativeUnitByteClearResult, 0, len(unitIndices))
	total := 0
	for _, rawIndex := range unitIndices {
		unitIndex := int(rawIndex)
		base := unitIndex * nativeRecordSize
		if base < 0 || base+nativeRecordSize > len(records) {
			return nil, 0, recordBoundsError(unitIndex)
		}
		record := records[base : base+nativeRecordSize]
		result := NativeUnitByteClearResult{UnitIndex: unitIndex}
		if record[fieldOffset] != 0 {
			record[fieldOffset] = 0
			effective := int(record[0x21])
			if record[0x20] > 8 && record[0x20] < 0x19 {
				effective += 30
			}
			result.Cleared = true
			result.RawValue = 4 * effective
			total += result.RawValue
		}
		results = append(results, result)
	}
	return results, total, nil
}
