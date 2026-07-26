package battle

import (
	"encoding/binary"
	"fmt"
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
	return ApplyNativeRawWordStepAtOffsets(records, unitIndices, rngState, 0x22, 0x48)
}

// ApplyNativeRawWordStepAtOffsets is the shared raw implementation used by
// the 0x22721 (+0x22/+0x48) and 0x22866 (+0x23/+0x4a) native branches.
func ApplyNativeRawWordStepAtOffsets(records []byte, unitIndices []byte, rngState uint16, markerOffset, wordOffset int) ([]NativeRawWordStepResult, uint16, int, error) {
	if markerOffset < 0 || markerOffset >= nativeRecordSize || wordOffset < 0 || wordOffset+2 > nativeRecordSize {
		return nil, rngState, 0, fmt.Errorf("native raw word offsets marker=%#x word=%#x out of bounds", markerOffset, wordOffset)
	}
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
		if record[markerOffset] != 0 {
			results = append(results, result)
			continue
		}
		rngState = fdother.NativeRNGStep(rngState)
		record[markerOffset] = byte(rngState%4 + 2)
		current := binary.LittleEndian.Uint16(record[wordOffset:])
		increment := int(math.Trunc(float64(current)*0.15 + 1.0))
		updated := current + uint16(increment)
		binary.LittleEndian.PutUint16(record[wordOffset:], updated)
		effective := int(record[0x21])
		if record[0x20] > 8 && record[0x20] < 0x19 {
			effective += 30
		}
		result.Processed = true
		result.Marker = record[markerOffset]
		result.Delta = uint16(increment)
		total += 2 * effective
		results = append(results, result)
	}
	return results, rngState, total, nil
}
