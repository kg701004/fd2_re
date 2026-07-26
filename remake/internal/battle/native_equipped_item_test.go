package battle

import "testing"

func TestNativeEquippedInventorySlotMatches1B83D(t *testing.T) {
	flags := []int{0x40, 0x40, 0, 0x40, 0x80, 0x80, 0, 0x80}
	slots := []int{0x90, 0x44, 0x55, 0xc0, 0xff, 0xff, 0x20, 0xff}
	if got, err := NativeEquippedInventorySlot(flags, slots, 0); err != nil || got != 1 {
		t.Fatalf("low-item first equipped slot=%d err=%v, want 1", got, err)
	}
	if got, err := NativeEquippedInventorySlot(flags, slots, 1); err != nil || got != 0 {
		t.Fatalf("high-item first equipped slot=%d err=%v, want 0", got, err)
	}
	if got, err := NativeEquippedInventorySlot(flags, slots, 0); err != nil || got < 0 {
		t.Fatalf("repeated lookup unexpectedly missing: %d err=%v", got, err)
	}
	if _, err := NativeEquippedInventorySlot(flags[:7], slots, 0); err == nil {
		t.Fatal("short input unexpectedly accepted")
	}
}
