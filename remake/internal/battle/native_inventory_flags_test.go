package battle

import "testing"

func TestNativeInventoryFlagsFromConstructorSource(t *testing.T) {
	flags, err := NativeInventoryFlagsFromSource([]int{0x44, 0x55, 0xff, 0x66, 0xff, 0xff, 0x77, 0xff})
	if err != nil {
		t.Fatal(err)
	}
	want := []int{0x40, 0x40, 0x80, 0x00, 0x80, 0x80, 0x00, 0x80}
	for i := range want {
		if flags[i] != want[i] {
			t.Fatalf("flags[%d]=%#x, want %#x (all=%#v)", i, flags[i], want[i], flags)
		}
	}
	collapsed, err := NativeInventoryFlagsFromSource([]int{0xff, 0x55, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff})
	if err != nil || collapsed[0] != 0x40 || collapsed[1] != 0x80 {
		t.Fatalf("collapsed first pair=%#v err=%v", collapsed, err)
	}
}

func TestNativeInventoryCompactEligibleUsesRawFlags(t *testing.T) {
	flags := []int{0x40, 0x40, 0x80, 0, 0x80, 0x80, 0, 0x80}
	slots := []int{0x44, 0x55, 0xff, 0x66, 0xff, 0xff, 0x77, 0xff}
	if ok, err := NativeInventoryCompactEligible(flags, slots, 0); err != nil || !ok {
		t.Fatalf("signed-nonnegative equipped item gate ok=%v err=%v", ok, err)
	}
	if ok, err := NativeInventoryCompactEligible(flags, slots, 1); err != nil || !ok {
		t.Fatalf("unequipped item gate ok=%v err=%v", ok, err)
	}
	if ok, err := NativeInventoryCompactEligible(flags, slots, 2); err != nil || !ok {
		t.Fatalf("second unequipped item gate ok=%v err=%v", ok, err)
	}
	if _, err := NativeInventoryCompactEligible(flags[:7], slots, 0); err == nil {
		t.Fatal("short raw flags unexpectedly accepted")
	}
}
