package battle

import "fmt"

// NativeItemMarkerClearRestoreRoute closes type 6/7 around 0x22af6.
// Nonzero target markers are cleared after a base-10 HP restore, and the
// dispatcher consumes the source slot. Player-facing status names are unknown.
type NativeItemMarkerClearRestoreRoute struct {
	ItemType         byte
	PresentationCode int
	MarkerOffset     int
	HPRestoreBase    int
	ConsumesSource   bool
}

func NativeItemMarkerClearRestoreRouteForType(itemType byte) (NativeItemMarkerClearRestoreRoute, bool) {
	switch itemType {
	case 6:
		return NativeItemMarkerClearRestoreRoute{
			ItemType: itemType, PresentationCode: 20,
			MarkerOffset: 0x25, HPRestoreBase: 10, ConsumesSource: true,
		}, true
	case 7:
		return NativeItemMarkerClearRestoreRoute{
			ItemType: itemType, PresentationCode: 21,
			MarkerOffset: 0x26, HPRestoreBase: 10, ConsumesSource: true,
		}, true
	default:
		return NativeItemMarkerClearRestoreRoute{}, false
	}
}

func ApplyNativeItemMarkerClearRestore(
	records []byte,
	targetIndices []byte,
	route NativeItemMarkerClearRestoreRoute,
	rngState uint16,
	sourceUnit, sourceSlot int,
) ([]NativeRawFlagRestoreResult, uint16, int, error) {
	verified, ok := NativeItemMarkerClearRestoreRouteForType(route.ItemType)
	if !ok || verified != route {
		return nil, rngState, 0, fmt.Errorf("native item marker-clear route is invalid: %#v", route)
	}
	sourceBase := sourceUnit * nativeRecordSize
	if sourceUnit < 0 || sourceBase < 0 || sourceBase+0x1a > len(records) {
		return nil, rngState, 0, recordBoundsError(sourceUnit)
	}
	if sourceSlot < 0 || sourceSlot >= 8 {
		return nil, rngState, 0, fmt.Errorf("native inventory slot %d is out of bounds", sourceSlot)
	}
	results, nextRNG, score, err := ApplyNativeRawFlagRestore(
		records, targetIndices, route.MarkerOffset, rngState,
	)
	if err != nil {
		return nil, rngState, 0, err
	}
	// Removal cannot fail after the preflight above.
	if err := RemoveNativeInventorySlot(records, sourceUnit, sourceSlot); err != nil {
		return nil, rngState, 0, err
	}
	return results, nextRNG, score, nil
}
