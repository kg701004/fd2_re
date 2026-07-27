package battle

import (
	"encoding/binary"
	"fmt"
)

// NativeItemMPRestoreRoute is the closed type-11 branch in 0x20c6f.
// Row word +0x0e is passed to 0x1c9dd, and the source slot is consumed after
// the target loop.
type NativeItemMPRestoreRoute struct {
	ItemType byte
	Amount   uint16
}

type NativeItemMPRestoreBatch struct {
	Results        []NativeRawRestoreResult
	SkippedTargets []int
	RNGState       uint16
	Score          int
}

func NativeItemMPRestoreRouteForType(itemType byte, amount uint16) (NativeItemMPRestoreRoute, bool) {
	if itemType != 11 {
		return NativeItemMPRestoreRoute{}, false
	}
	return NativeItemMPRestoreRoute{ItemType: itemType, Amount: amount}, true
}

// ApplyNativeItemMPRestore reproduces the mutation transaction of the type-11
// branch without presentation callbacks. A target whose max-MP word +0x46 is
// zero is skipped without advancing RNG. Valid targets use 0x1c9dd in list
// order, then 0x1b8e7 consumes the source slot.
func ApplyNativeItemMPRestore(
	records []byte,
	targetIndices []byte,
	route NativeItemMPRestoreRoute,
	rngState uint16,
	sourceUnit, sourceSlot int,
) (NativeItemMPRestoreBatch, error) {
	verified, ok := NativeItemMPRestoreRouteForType(route.ItemType, route.Amount)
	if !ok || verified != route {
		return NativeItemMPRestoreBatch{RNGState: rngState}, fmt.Errorf("native item MP restore route is invalid: %#v", route)
	}
	for _, rawIndex := range targetIndices {
		if int(rawIndex) >= len(records)/nativeRecordSize {
			return NativeItemMPRestoreBatch{RNGState: rngState}, recordBoundsError(int(rawIndex))
		}
	}
	sourceBase := sourceUnit * nativeRecordSize
	if sourceUnit < 0 || sourceBase < 0 || sourceBase+0x1a > len(records) {
		return NativeItemMPRestoreBatch{RNGState: rngState}, recordBoundsError(sourceUnit)
	}
	if sourceSlot < 0 || sourceSlot >= 8 {
		return NativeItemMPRestoreBatch{RNGState: rngState}, fmt.Errorf("native inventory slot %d is out of bounds", sourceSlot)
	}
	result := NativeItemMPRestoreBatch{
		Results:        make([]NativeRawRestoreResult, 0, len(targetIndices)),
		SkippedTargets: make([]int, 0),
		RNGState:       rngState,
	}
	for _, rawIndex := range targetIndices {
		unit := int(rawIndex)
		record := records[unit*nativeRecordSize:]
		if binary.LittleEndian.Uint16(record[0x46:0x48]) == 0 {
			result.SkippedTargets = append(result.SkippedTargets, unit)
			continue
		}
		entry, err := ApplyNativeRawMPRestore(records, unit, int(route.Amount), result.RNGState)
		if err != nil {
			return NativeItemMPRestoreBatch{RNGState: rngState}, err
		}
		result.Results = append(result.Results, entry)
		result.RNGState = entry.RNGState
		result.Score += entry.Score
	}
	// Removal cannot fail after the preflight above.
	if err := RemoveNativeInventorySlot(records, sourceUnit, sourceSlot); err != nil {
		return NativeItemMPRestoreBatch{RNGState: rngState}, err
	}
	return result, nil
}
