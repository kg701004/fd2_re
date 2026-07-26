package battle

import "fmt"

// NativeRawFlagRestoreResult records the raw result of one 0x22af6 flag cell.
type NativeRawFlagRestoreResult struct {
	TargetIndex int
	Applied     bool
	Restore     NativeRawRestoreResult
}

// ApplyNativeRawFlagRestore reproduces the proven 0x22af6 branch: each target
// byte is paired with a caller-owned flag byte; nonzero flags invoke
// 0x1c916(target, 10), are then cleared, and contribute the native
// effective-value*4 accumulator. Flag meaning and UI remain caller-owned.
func ApplyNativeRawFlagRestore(records []byte, targetIndices, flags []byte, rngState uint16) ([]NativeRawFlagRestoreResult, uint16, int, error) {
	if len(targetIndices) != len(flags) {
		return nil, rngState, 0, fmt.Errorf("native flag restore target/flag lengths differ: %d/%d", len(targetIndices), len(flags))
	}
	for _, rawIndex := range targetIndices {
		if int(rawIndex) >= len(records)/nativeRecordSize {
			return nil, rngState, 0, recordBoundsError(int(rawIndex))
		}
	}
	results := make([]NativeRawFlagRestoreResult, 0, len(targetIndices))
	total := 0
	for i, rawIndex := range targetIndices {
		result := NativeRawFlagRestoreResult{TargetIndex: int(rawIndex)}
		if flags[i] != 0 {
			restore, err := ApplyNativeRawHPRestore(records, int(rawIndex), 10, rngState)
			if err != nil {
				return nil, rngState, 0, err
			}
			rngState = restore.RNGState
			record := records[int(rawIndex)*nativeRecordSize:]
			effective := int(record[0x21])
			if record[0x20] > 8 && record[0x20] < 0x19 {
				effective += 0x1e
			}
			flags[i] = 0
			total += effective * 4
			result.Applied, result.Restore = true, restore
		}
		results = append(results, result)
	}
	return results, rngState, total, nil
}
