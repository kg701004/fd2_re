package battle

import (
	"encoding/binary"
	"math"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

// NativeRawWordStepResult records the mutation-only portion of 0x22721.
// Offsets and values remain raw; no gameplay effect is inferred.
type NativeRawWordStepResult struct {
	UnitIndex int
	Processed bool
	Marker    byte
	Delta     uint16
}

// ApplyNativeRawWordStep reproduces 0x22721's per-unit branch.  Each index
// addresses one 0x50-byte record. A nonzero record+0x22 is skipped. Otherwise
// the shared 0x4e893 RNG advances, marker+0x22 receives (rng%4)+2, and the
// word at +0x48 gains trunc(word*0.15+1) with native toward-zero semantics.
// The returned score is the raw 2*effective(+0x21) accumulator. Renderer and
// presentation calls are deliberately excluded.
func ApplyNativeRawWordStep(records []byte, unitIndices []byte, rngState uint16) ([]NativeRawWordStepResult, uint16, int, error) {
	for _, rawIndex := range unitIndices {
		base := int(rawIndex) * nativeRecordSize
		if base < 0 || base+nativeRecordSize > len(records) {
			return nil, rngState, 0, recordBoundsError(int(rawIndex))
		}
	}
	results := make([]NativeRawWordStepResult, 0, len(unitIndices))
	total := 0
	for _, rawIndex := range unitIndices {
		unitIndex := int(rawIndex)
		base := unitIndex * nativeRecordSize
		record := records[base : base+nativeRecordSize]
		result := NativeRawWordStepResult{UnitIndex: unitIndex}
		if record[0x22] != 0 {
			results = append(results, result)
			continue
		}
		rngState = fdother.NativeRNGStep(rngState)
		record[0x22] = byte(rngState%4 + 2)
		current := binary.LittleEndian.Uint16(record[0x48:])
		increment := int(math.Trunc(float64(current)*0.15 + 1.0))
		updated := current + uint16(increment)
		binary.LittleEndian.PutUint16(record[0x48:], updated)
		effective := int(record[0x21])
		if record[0x20] > 8 && record[0x20] < 0x19 {
			effective += 30
		}
		result.Processed = true
		result.Marker = record[0x22]
		result.Delta = uint16(increment)
		total += 2 * effective
		results = append(results, result)
	}
	return results, rngState, total, nil
}
