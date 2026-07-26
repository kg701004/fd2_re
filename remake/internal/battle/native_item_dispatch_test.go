package battle

import "testing"

func TestNativeItemEffectRouteForTypePreservesRawBranches(t *testing.T) {
	cases := []struct {
		itemType           byte
		primary, secondary uint32
		arg2, arg5, arg7   int
	}{
		{5, 0x211a4, 0, 0, 0, 0},
		{6, 0x22af6, 0, 20, 37, 0},
		{8, 0x21082, 0, 55, 0, 17},
		{11, 0x1c4cc, 0x1c2da, 13, 0, 0},
		{20, 0x1c4cc, 0x1cd17, 0, 0, 0},
		{22, 0x22d1b, 0, 22, 39, 0},
		{23, 0x2218a, 0, 0, 0, 0},
	}
	for _, tc := range cases {
		route, ok := NativeItemEffectRouteForType(tc.itemType, 0x1234)
		if !ok || route.Primary != tc.primary || route.Secondary != tc.secondary ||
			route.Arg2 != tc.arg2 || route.Arg5 != tc.arg5 || route.Arg7 != tc.arg7 || route.Word != 0x1234 {
			t.Fatalf("type %d route = %#v, want primary=%#x secondary=%#x args=(%d,%d,%d)", tc.itemType, route, tc.primary, tc.secondary, tc.arg2, tc.arg5, tc.arg7)
		}
	}
}

func TestNativeItemEffectRouteRejectsUnknownType(t *testing.T) {
	if route, ok := NativeItemEffectRouteForType(0, 0); ok || route.Primary != 0 {
		t.Fatalf("unknown item type must fail closed: %#v, %v", route, ok)
	}
}
