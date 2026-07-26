package battle

import (
	"encoding/binary"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

// NativeRawDamageResult exposes only the proven 0x1c81f HP mutation.
type NativeRawDamageResult struct {
	UnitIndex int
	Rolled    int
	Actual    int
	RNGState  uint16
}

// ApplyNativeRawHPDamage reproduces the raw write portion of 0x1c81f:
// amount*9/10 + (RNG%100)*amount/1000 is subtracted from +0x40 and clamped at
// zero. The separate native presentation-score branch is intentionally not
// inferred here.
func ApplyNativeRawHPDamage(records []byte, unitIndex, amount int, rngState uint16) (NativeRawDamageResult, error) {
	if unitIndex < 0 || unitIndex >= len(records)/nativeRecordSize {
		return NativeRawDamageResult{}, recordBoundsError(unitIndex)
	}
	if amount < 0 {
		return NativeRawDamageResult{}, fmt.Errorf("native damage amount %d is negative", amount)
	}
	record := records[unitIndex*nativeRecordSize:]
	current := int(binary.LittleEndian.Uint16(record[0x40:0x42]))
	nextRNG := fdother.NativeRNGStep(rngState)
	rolled := amount*9/10 + int(nextRNG%100)*amount/1000
	next := current - rolled
	if next < 0 {
		next = 0
	}
	binary.LittleEndian.PutUint16(record[0x40:0x42], uint16(next))
	return NativeRawDamageResult{UnitIndex: unitIndex, Rolled: rolled, Actual: current - next, RNGState: nextRNG}, nil
}
