package fdicon

import "testing"

func TestBlitNativeForegroundLayerMatches12AC6Schedule(t *testing.T) {
	bank := nativeLayerBank()
	// index 1/2 are selected by foreground tiles 0/1 respectively.
	bank.Sprites[1].Pixels[0] = 0x2a
	bank.Sprites[2].Pixels[0] = 0x2b
	dst := make([]byte, NativeMapStride*160)
	cells := []NativeTerrainCell{{Tile: 0, BlitMode: 0xff}, {Tile: 1, BlitMode: 0xff}}
	controls := []byte{0x80, 0, 0, 0, 0x80, 0, 0, 0}
	unit := NativeForegroundLayerEntry{X: 0, Y: 1, Pose: 0}
	if err := bank.BlitNativeForegroundLayer(dst, NativeMapStride, []NativeForegroundLayerEntry{unit}, 1, cells, controls, 0, 0, 12, 7, 0, nil); err != nil {
		t.Fatal(err)
	}
	// Native order is (x,y) then (x,y-1); both coordinates retain their own
	// descriptor selection rather than reusing the unit's map selector.
	upper := 0x8088
	if got, want := dst[upper], byte(0x2a); got != want {
		t.Fatalf("upper foreground pixel=%#x, want %#x", got, want)
	}
	current := 0x8088 + NativeSize*NativeMapStride
	if got, want := dst[current], byte(0x2b); got != want {
		t.Fatalf("current foreground pixel=%#x, want %#x", got, want)
	}
}

func TestBlitNativeForegroundLayerFailsBeforePartialFrame(t *testing.T) {
	dst := make([]byte, NativeMapStride*160)
	cells := []NativeTerrainCell{{Tile: 0, BlitMode: 0}}
	controls := []byte{0x80, 0, 0, 0}
	unit := NativeForegroundLayerEntry{X: 0, Y: 0}
	if err := nativeLayerBank().BlitNativeForegroundLayer(dst, NativeMapStride, []NativeForegroundLayerEntry{unit}, 1, cells, controls, 0, 0, 12, 7, 0, nil); err == nil {
		t.Fatal("missing LUT was accepted")
	}
	if dst[0x8088] != 0 {
		t.Fatal("failed foreground layer partially modified destination")
	}
}
