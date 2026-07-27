package battle

import "testing"

func TestNativeItemEffectRowOffset(t *testing.T) {
	for _, tc := range []struct {
		item int
		want int
	}{
		{0, 0},
		{1, 0x17},
		{0xff, 0x17 * 0xff},
	} {
		got, err := NativeItemEffectRowOffset(tc.item)
		if err != nil || got != tc.want {
			t.Fatalf("item %#x: got %#x, err=%v; want %#x", tc.item, got, err, tc.want)
		}
	}
	for _, item := range []int{-1, 0x100} {
		if _, err := NativeItemEffectRowOffset(item); err == nil {
			t.Fatalf("item %#x unexpectedly accepted", item)
		}
	}
}

func TestNativeItemWordDeltaRouteForTypePreservesRawDispatch(t *testing.T) {
	tests := []struct {
		itemType, field, presentation int
		baseStat                      NativeItemBaseStat
	}{
		{8, 0x37, 0x11, NativeItemBaseAP},
		{9, 0x39, 0x12, NativeItemBaseDP},
		{0xa, 0x3e, 0x13, NativeItemBaseDX},
	}
	for _, tc := range tests {
		route, ok := NativeItemWordDeltaRouteForType(tc.itemType)
		if !ok || route.ItemType != tc.itemType || route.BaseStat != tc.baseStat ||
			route.FieldOffset != tc.field || route.PresentationCode != tc.presentation {
			t.Fatalf("type %#x route=%#v ok=%v", tc.itemType, route, ok)
		}
	}
	if _, ok := NativeItemWordDeltaRouteForType(7); ok {
		t.Fatal("unsupported item type became a word-delta route")
	}
}
