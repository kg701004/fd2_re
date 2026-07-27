package battle

import (
	"encoding/binary"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

// NativeRawRestoreResult exposes the proven state mutation and raw score from
// 0x1c916.  Score is kept unnamed: callers may still have to prove how the
// native presentation accumulator is consumed.
type NativeRawRestoreResult struct {
	UnitIndex int
	Rolled    int
	Actual    int
	Score     int
	RNGState  uint16
}

// NativeRawRestoreBatch is the mutation-only result of the 0x211a4 target
// loop.  Presentation queue writes and indexed animation remain outside this
// adapter.
type NativeRawRestoreBatch struct {
	Results  []NativeRawRestoreResult
	RNGState uint16
	Score    int
}

// ApplyNativeRawHPRestoreList reproduces the per-target mutation loop in
// 0x211a4(actor,count,targetBytes,amount).  Official IDA 9.4 confirms that
// 0x20c6f passes its a3/a4 target count/list unchanged and supplies item-row
// word +0x0e as amount.  Inputs are preflighted so an invalid later target
// cannot leave an earlier record partially mutated.
func ApplyNativeRawHPRestoreList(records []byte, targetIndices []byte, amount int, rngState uint16) (NativeRawRestoreBatch, error) {
	if amount < 0 {
		return NativeRawRestoreBatch{RNGState: rngState}, fmt.Errorf("native restore amount %d is negative", amount)
	}
	for _, rawIndex := range targetIndices {
		if int(rawIndex) >= len(records)/nativeRecordSize {
			return NativeRawRestoreBatch{RNGState: rngState}, recordBoundsError(int(rawIndex))
		}
	}
	result := NativeRawRestoreBatch{
		Results:  make([]NativeRawRestoreResult, 0, len(targetIndices)),
		RNGState: rngState,
	}
	for _, rawIndex := range targetIndices {
		entry, err := ApplyNativeRawHPRestore(records, int(rawIndex), amount, result.RNGState)
		if err != nil {
			return NativeRawRestoreBatch{RNGState: rngState}, err
		}
		result.Results = append(result.Results, entry)
		result.RNGState = entry.RNGState
		result.Score += entry.Score
	}
	return result, nil
}

// ApplyNativeRawHPRestore reproduces the mutation core of 0x1c916 on a
// 0x50-byte runtime record. The native routine advances the shared 16-bit RNG,
// applies toward-zero integer arithmetic, clamps +0x40 to +0x42, and adds a
// derived raw score only when record +0x07 is below 0x4b. No gameplay label is
// assigned to those raw bytes or to the score.
func ApplyNativeRawHPRestore(records []byte, unitIndex, amount int, rngState uint16) (NativeRawRestoreResult, error) {
	if unitIndex < 0 || unitIndex >= len(records)/nativeRecordSize {
		return NativeRawRestoreResult{}, recordBoundsError(unitIndex)
	}
	if amount < 0 {
		return NativeRawRestoreResult{}, fmt.Errorf("native restore amount %d is negative", amount)
	}
	record := records[unitIndex*nativeRecordSize:]
	current := int(binary.LittleEndian.Uint16(record[0x40:0x42]))
	max := int(binary.LittleEndian.Uint16(record[0x42:0x44]))
	nextRNG := fdother.NativeRNGStep(rngState)
	rolled := amount*9/10 + int(nextRNG%100)*amount/1000
	next := current + rolled
	if next > max {
		next = max
	}
	if next < 0 {
		next = 0
	}
	binary.LittleEndian.PutUint16(record[0x40:0x42], uint16(next))
	delta := next - current
	score := 0
	if record[7] < 0x4b && max != 0 {
		effective := int(record[0x21])
		if record[0x20] > 8 && record[0x20] < 0x19 {
			effective += 0x1e
		}
		score = (40 * effective * delta) / max
	}
	return NativeRawRestoreResult{UnitIndex: unitIndex, Rolled: rolled, Actual: delta, Score: score, RNGState: nextRNG}, nil
}

// ApplyNativeRawMPRestore is the sibling 0x1c9dd mutation. It uses raw
// +0x44/+0x46 and the same RNG/amount arithmetic, but its score path uses only
// byte +0x21 (the HP routine has an additional class-range adjustment).
func ApplyNativeRawMPRestore(records []byte, unitIndex, amount int, rngState uint16) (NativeRawRestoreResult, error) {
	if unitIndex < 0 || unitIndex >= len(records)/nativeRecordSize {
		return NativeRawRestoreResult{}, recordBoundsError(unitIndex)
	}
	if amount < 0 {
		return NativeRawRestoreResult{}, fmt.Errorf("native restore amount %d is negative", amount)
	}
	record := records[unitIndex*nativeRecordSize:]
	current := int(binary.LittleEndian.Uint16(record[0x44:0x46]))
	max := int(binary.LittleEndian.Uint16(record[0x46:0x48]))
	nextRNG := fdother.NativeRNGStep(rngState)
	rolled := amount*9/10 + int(nextRNG%100)*amount/1000
	next := current + rolled
	if next > max {
		next = max
	}
	if next < 0 {
		next = 0
	}
	binary.LittleEndian.PutUint16(record[0x44:0x46], uint16(next))
	delta := next - current
	score := 0
	if record[7] < 0x4b && max != 0 {
		score = (40 * int(record[0x21]) * delta) / max
	}
	return NativeRawRestoreResult{UnitIndex: unitIndex, Rolled: rolled, Actual: delta, Score: score, RNGState: nextRNG}, nil
}
