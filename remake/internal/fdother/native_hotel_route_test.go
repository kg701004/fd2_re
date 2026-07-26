package fdother

import "testing"

func TestResolveNativeHotelServiceRoutePreservesRawBranches(t *testing.T) {
	checks := []struct {
		selector  byte
		primary   uint32
		secondary uint32
	}{
		{0, 0x2ffa5, 0},
		{1, 0x30012, 0},
		{2, 0x301f4, 0},
		{3, 0x19953, 0x197e5},
	}
	for _, tc := range checks {
		got, ok := ResolveNativeHotelServiceRoute(tc.selector)
		if !ok || got.ResourceID != 13 || got.Primary != tc.primary || got.Secondary != tc.secondary {
			t.Fatalf("route(%d) = %#v,%v; want primary=%#x secondary=%#x", tc.selector, got, ok, tc.primary, tc.secondary)
		}
	}
	if got, ok := ResolveNativeHotelServiceRoute(4); ok || got != (NativeHotelServiceRoute{}) {
		t.Fatalf("invalid selector accepted: %#v,%v", got, ok)
	}
}
