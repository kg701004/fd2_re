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
