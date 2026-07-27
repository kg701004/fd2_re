package battle

import "fmt"

// NativeItemHITEVStepRoute is the closed type-12 branch in 0x20c6f. It calls
// 0x22997, which gates on marker +0x24 and adds 15 to the derived HIT/EV words
// +0x4c/+0x4e. The dispatcher retains the source item.
type NativeItemHITEVStepRoute struct {
	ItemType       byte
	Increment      uint16
	ConsumesSource bool
}

func NativeItemHITEVStepRouteForType(itemType byte) (NativeItemHITEVStepRoute, bool) {
	if itemType != 12 {
		return NativeItemHITEVStepRoute{}, false
	}
	return NativeItemHITEVStepRoute{ItemType: itemType, Increment: 15, ConsumesSource: false}, true
}

// ApplyNativeItemHITEVStep executes the proven type-12 mutation without its
// presentation callbacks. ApplyNativeRawPairStep preserves list order,
// marker-gated RNG, 16-bit wrapping, and atomic target preflight.
func ApplyNativeItemHITEVStep(
	records []byte,
	unitIndices []byte,
	route NativeItemHITEVStepRoute,
	rngState uint16,
) ([]NativeRawPairStepResult, uint16, int, error) {
	verified, ok := NativeItemHITEVStepRouteForType(route.ItemType)
	if !ok || verified != route {
		return nil, rngState, 0, fmt.Errorf("native item HIT/EV route is invalid: %#v", route)
	}
	return ApplyNativeRawPairStep(records, unitIndices, rngState)
}
