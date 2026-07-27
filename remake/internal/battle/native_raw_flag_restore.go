package battle

import "fmt"

// NativeRawFlagRestoreResult records the raw result of one 0x22af6 flag cell.
type NativeRawFlagRestoreResult struct {
	TargetIndex int
	Applied     bool
	Restore     NativeRawRestoreResult
}

// ApplyNativeRawFlagRestore reproduces the proven 0x22af6 branch. For each
// target, a nonzero byte at record+markerOffset invokes 0x1c916(target,10),
// is then cleared in that same runtime record, and contributes the native
// effective-value*4 accumulator. Marker meaning and UI remain caller-owned.
func ApplyNativeRawFlagRestore(records []byte, targetIndices []byte, markerOffset int, rngState uint16) ([]NativeRawFlagRestoreResult, uint16, int, error) {
	if markerOffset < 0 || markerOffset >= nativeRecordSize {
		return nil, rngState, 0, fmt.Errorf("native flag restore marker offset %#x is out of bounds", markerOffset)
	}
	for _, rawIndex := range targetIndices {
		if int(rawIndex) >= len(records)/nativeRecordSize {
			return nil, rngState, 0, recordBoundsError(int(rawIndex))
		}
	}
	results := make([]NativeRawFlagRestoreResult, 0, len(targetIndices))
	total := 0
	for _, rawIndex := range targetIndices {
		result := NativeRawFlagRestoreResult{TargetIndex: int(rawIndex)}
		record := records[int(rawIndex)*nativeRecordSize:]
		if record[markerOffset] != 0 {
			restore, err := ApplyNativeRawHPRestore(records, int(rawIndex), 10, rngState)
			if err != nil {
				return nil, rngState, 0, err
			}
			rngState = restore.RNGState
			effective := int(record[0x21])
			if record[0x20] > 8 && record[0x20] < 0x19 {
				effective += 0x1e
			}
			record[markerOffset] = 0
			total += effective * 4
			result.Applied, result.Restore = true, restore
		}
		results = append(results, result)
	}
	return results, rngState, total, nil
}
