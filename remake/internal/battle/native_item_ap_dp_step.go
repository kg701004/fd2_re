package battle

import "fmt"

type NativeItemDerivedStat string

const (
	NativeItemDerivedAP NativeItemDerivedStat = "ap"
	NativeItemDerivedDP NativeItemDerivedStat = "dp"
)

// NativeItemAPDPStepRoute closes the type-15/type-16 branches in 0x20c6f.
// Both retain the source item. Type 15 gates marker +0x23 and increases
// derived DP +0x4a; type 16 gates +0x22 and increases derived AP +0x48.
type NativeItemAPDPStepRoute struct {
	ItemType       byte
	DerivedStat    NativeItemDerivedStat
	MarkerOffset   int
	WordOffset     int
	ConsumesSource bool
}

func NativeItemAPDPStepRouteForType(itemType byte) (NativeItemAPDPStepRoute, bool) {
	switch itemType {
	case 15:
		return NativeItemAPDPStepRoute{
			ItemType: itemType, DerivedStat: NativeItemDerivedDP,
			MarkerOffset: 0x23, WordOffset: 0x4a,
		}, true
	case 16:
		return NativeItemAPDPStepRoute{
			ItemType: itemType, DerivedStat: NativeItemDerivedAP,
			MarkerOffset: 0x22, WordOffset: 0x48,
		}, true
	default:
		return NativeItemAPDPStepRoute{}, false
	}
}

// ApplyNativeItemAPDPStep executes the proven retained-item mutation without
// presentation callbacks. The shared primitive preserves marker-gated RNG,
// trunc(current*0.15+1), 16-bit wrapping, list order and atomic preflight.
func ApplyNativeItemAPDPStep(
	records []byte,
	unitIndices []byte,
	route NativeItemAPDPStepRoute,
	rngState uint16,
) ([]NativeRawWordStepResult, uint16, int, error) {
	verified, ok := NativeItemAPDPStepRouteForType(route.ItemType)
	if !ok || verified != route {
		return nil, rngState, 0, fmt.Errorf("native item AP/DP route is invalid: %#v", route)
	}
	return ApplyNativeRawWordStepAtOffsets(
		records, unitIndices, rngState, route.MarkerOffset, route.WordOffset,
	)
}
