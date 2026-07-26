package fdicon

import "testing"

func nativeLayerBank() *Bank {
	bank := &Bank{Sprites: make([]Sprite, 12)}
	for i := range bank.Sprites {
		pixels := make([]byte, NativeSize*NativeSize)
		mask := make([]byte, NativeSize*NativeSize)
		pixels[0], mask[0] = byte(0x10+i), 1
		bank.Sprites[i] = Sprite{Pixels: pixels, Mask: mask, RemapMask: make([]byte, NativeSize*NativeSize)}
	}
	return bank
}

func TestBlitNativeUnitLayerMatches127E0OrderAndBranches(t *testing.T) {
	cache := &NativeSelectorCache{}
	if _, err := cache.SlotFor(0); err != nil {
		t.Fatal(err)
	}
	dst := make([]byte, NativeMapStride*100)
	units := []NativeUnitLayerEntry{
		{X: 0, Y: 0, Slot: 0, Pose: 0, Flags: 0},
		{X: 1, Y: 0, Slot: 0, Pose: 0, Flags: 0x80},
		{X: 2, Y: 0, Slot: 0, Pose: 0, Inactive: true},
	}
	if err := nativeLayerBank().BlitNativeUnitLayer(dst, NativeMapStride, cache, units, 0, 0, 12, 7, 0, 0, 0); err != nil {
		t.Fatal(err)
	}
	base, _ := NativePlacementOffset(0, 0, 0, 0, 0, 0, 0, false)
	if got, want := dst[base], byte(0x10); got != want {
		t.Fatalf("raw unit pixel=%#x, want %#x", got, want)
	}
	if got, want := dst[base+NativeSize], byte(0x18); got != want {
		t.Fatalf("band unit pixel=%#x, want %#x", got, want)
	}
	if got := dst[base+2*NativeSize]; got != 0 {
		t.Fatalf("inactive unit wrote %#x", got)
	}
}

func TestBlitNativeUnitLayerFailsBeforePartialFrame(t *testing.T) {
	cache := &NativeSelectorCache{}
	if _, err := cache.SlotFor(0); err != nil {
		t.Fatal(err)
	}
	dst := make([]byte, NativeMapStride*100)
	units := []NativeUnitLayerEntry{{X: 0, Y: 0, Slot: 0, Pose: 0}, {X: 1, Y: 0, Slot: 7, Pose: 0}}
	if err := nativeLayerBank().BlitNativeUnitLayer(dst, NativeMapStride, cache, units, 0, 0, 12, 7, 0, 0, 0); err == nil {
		t.Fatal("unknown slot was accepted")
	}
	base, _ := NativePlacementOffset(0, 0, 0, 0, 0, 0, 0, false)
	if dst[base] != 0 {
		t.Fatal("failed layer partially modified destination")
	}
}
