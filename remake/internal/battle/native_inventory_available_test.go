package battle

import "testing"

func TestNativeInventoryAvailableCountUsesSignedRawFlags(t *testing.T) {
	count, err := NativeInventoryAvailableCount([]int{0x40, 0x40, 0, 0x80, 0x80, 0, 0x80, 0x80})
	if err != nil || count != 4 {
		t.Fatalf("available count=%d err=%v, want 4", count, err)
	}
	if _, err := NativeInventoryAvailableCount([]int{0, 0, 0}); err == nil {
		t.Fatal("short raw flag input unexpectedly accepted")
	}
}
