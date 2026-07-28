package fdother

import "testing"

func TestResolveNativeShopServiceRoutePreservesResourceAndCallee(t *testing.T) {
	checks := []struct {
		variant  byte
		resource byte
		selector byte
		callee   uint32
		kind     NativeShopServiceKind
	}{
		{0, 12, 0, 0x2f0b0, NativeShopPurchase},
		{3, 29, 1, 0x2f642, NativeShopSell},
		{5, 63, 2, 0x2f883, NativeShopEquip},
		{7, 12, 3, 0x2f8ea, NativeShopTransfer},
	}
	for _, tc := range checks {
		got, ok := ResolveNativeShopServiceRoute(tc.variant, tc.selector)
		if !ok || got.ResourceID != tc.resource || got.Callee != tc.callee ||
			got.HubVariant != tc.variant || got.Kind != tc.kind {
			t.Fatalf("route(%d,%d) = %#v,%v; want resource=%d callee=%#x", tc.variant, tc.selector, got, ok, tc.resource, tc.callee)
		}
	}
	if got, ok := ResolveNativeShopServiceRoute(0, 4); ok || got != (NativeShopServiceRoute{}) {
		t.Fatalf("invalid selector accepted: %#v,%v", got, ok)
	}
}
