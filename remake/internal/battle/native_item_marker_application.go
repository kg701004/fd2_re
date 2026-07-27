package battle

import "fmt"

// NativeItemMarkerApplicationRoute closes the type-14/type-22 item callers
// around 0x22d1b. Both retain the source, use a 50-percent RNG gate, apply
// HP damage with base amount 10 on success, then write a third-RNG marker.
// The marker's player-facing status name remains unknown.
type NativeItemMarkerApplicationRoute struct {
	ItemType         byte
	PresentationCode int
	MarkerOffset     int
	HPDamageBase     int
	ConsumesSource   bool
}

func NativeItemMarkerApplicationRouteForType(itemType byte) (NativeItemMarkerApplicationRoute, bool) {
	switch itemType {
	case 14:
		return NativeItemMarkerApplicationRoute{
			ItemType: itemType, PresentationCode: 27,
			MarkerOffset: 0x26, HPDamageBase: 10,
		}, true
	case 22:
		return NativeItemMarkerApplicationRoute{
			ItemType: itemType, PresentationCode: 22,
			MarkerOffset: 0x27, HPDamageBase: 10,
		}, true
	default:
		return NativeItemMarkerApplicationRoute{}, false
	}
}

// ApplyNativeItemMarkerApplication executes the proven retained-item mutation.
// ApplyNativeRawApplication preserves marker/class gates, all three RNG steps,
// HP damage, list order, 16-bit HP behavior and atomic target preflight.
func ApplyNativeItemMarkerApplication(
	records []byte,
	targetIndices []byte,
	route NativeItemMarkerApplicationRoute,
	rngState uint16,
) ([]NativeRawApplicationResult, uint16, int, error) {
	verified, ok := NativeItemMarkerApplicationRouteForType(route.ItemType)
	if !ok || verified != route {
		return nil, rngState, 0, fmt.Errorf("native item marker route is invalid: %#v", route)
	}
	return ApplyNativeRawApplication(records, targetIndices, route.MarkerOffset, rngState)
}
