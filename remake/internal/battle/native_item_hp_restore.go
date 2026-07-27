package battle

import "fmt"

// NativeItemHPRestoreRoute is the closed type-5/type-13 branch contract in
// 0x20c6f. Both routes call 0x211a4 with row word +0x0e as the HP restore
// amount. Only type 5 continues through 0x1b8e7 and consumes the source slot;
// type 13 retains it.
type NativeItemHPRestoreRoute struct {
	ItemType       byte
	Amount         uint16
	ConsumesSource bool
}

func NativeItemHPRestoreRouteForType(itemType byte, amount uint16) (NativeItemHPRestoreRoute, bool) {
	switch itemType {
	case 5:
		return NativeItemHPRestoreRoute{ItemType: itemType, Amount: amount, ConsumesSource: true}, true
	case 13:
		return NativeItemHPRestoreRoute{ItemType: itemType, Amount: amount, ConsumesSource: false}, true
	default:
		return NativeItemHPRestoreRoute{}, false
	}
}

// ApplyNativeItemHPRestore executes the proven mutation transaction without
// renderer/SFX callbacks. Target-list bounds and the optional source removal
// are preflighted before any HP is changed.
func ApplyNativeItemHPRestore(
	records []byte,
	targetIndices []byte,
	route NativeItemHPRestoreRoute,
	rngState uint16,
	sourceUnit, sourceSlot int,
) (NativeRawRestoreBatch, error) {
	verified, ok := NativeItemHPRestoreRouteForType(route.ItemType, route.Amount)
	if !ok || verified != route {
		return NativeRawRestoreBatch{RNGState: rngState}, fmt.Errorf("native item HP restore route is invalid: %#v", route)
	}
	for _, rawIndex := range targetIndices {
		if int(rawIndex) >= len(records)/nativeRecordSize {
			return NativeRawRestoreBatch{RNGState: rngState}, recordBoundsError(int(rawIndex))
		}
	}
	if route.ConsumesSource {
		base := sourceUnit * nativeRecordSize
		if sourceUnit < 0 || base < 0 || base+0x1a > len(records) {
			return NativeRawRestoreBatch{RNGState: rngState}, recordBoundsError(sourceUnit)
		}
		if sourceSlot < 0 || sourceSlot >= 8 {
			return NativeRawRestoreBatch{RNGState: rngState}, fmt.Errorf("native inventory slot %d is out of bounds", sourceSlot)
		}
	}
	result, err := ApplyNativeRawHPRestoreList(records, targetIndices, int(route.Amount), rngState)
	if err != nil {
		return NativeRawRestoreBatch{RNGState: rngState}, err
	}
	if route.ConsumesSource {
		// Removal cannot fail after the preflight above.
		if err := RemoveNativeInventorySlot(records, sourceUnit, sourceSlot); err != nil {
			return NativeRawRestoreBatch{RNGState: rngState}, err
		}
	}
	return result, nil
}
