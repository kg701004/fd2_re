package battle

import (
	"encoding/binary"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

// NativeRawPairStepResult records the mutation-only portion of 0x22997.
type NativeRawPairStepResult struct {
	UnitIndex int
	Processed bool
	Marker    byte
}

// ApplyNativeRawPairStep reproduces 0x22997: skip a nonzero marker at +0x24;
// otherwise advance the shared RNG, write marker=(rng%4)+2, and add 0x0f to
// both raw words at +0x4c and +0x4e. The raw score is 2*effective(+0x21).
func ApplyNativeRawPairStep(records []byte, unitIndices []byte, rngState uint16) ([]NativeRawPairStepResult, uint16, int, error) {
	for _, rawIndex := range unitIndices {
		base := int(rawIndex) * nativeRecordSize
		if base < 0 || base+nativeRecordSize > len(records) {
			return nil, rngState, 0, recordBoundsError(int(rawIndex))
		}
	}
	results := make([]NativeRawPairStepResult, 0, len(unitIndices))
	total := 0
	for _, rawIndex := range unitIndices {
		unitIndex := int(rawIndex)
		base := unitIndex * nativeRecordSize
		record := records[base : base+nativeRecordSize]
		result := NativeRawPairStepResult{UnitIndex: unitIndex}
		if record[0x24] != 0 {
			results = append(results, result)
			continue
		}
		rngState = fdother.NativeRNGStep(rngState)
		record[0x24] = byte(rngState%4 + 2)
		binary.LittleEndian.PutUint16(record[0x4c:], binary.LittleEndian.Uint16(record[0x4c:])+0x0f)
		binary.LittleEndian.PutUint16(record[0x4e:], binary.LittleEndian.Uint16(record[0x4e:])+0x0f)
		effective := int(record[0x21])
		if record[0x20] > 8 && record[0x20] < 0x19 {
			effective += 30
		}
		result.Processed = true
		result.Marker = record[0x24]
		total += 2 * effective
		results = append(results, result)
	}
	return results, rngState, total, nil
}
