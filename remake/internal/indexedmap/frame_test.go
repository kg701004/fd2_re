package indexedmap

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
)

func solid(v byte) fdicon.Sprite {
	pixels, mask := make([]byte, 24*24), make([]byte, 24*24)
	for i := range pixels {
		pixels[i], mask[i] = v, 1
	}
	return fdicon.Sprite{Pixels: pixels, Mask: mask, RemapMask: make([]byte, 24*24)}
}

func bank(n int, v byte) *fdicon.Bank {
	b := &fdicon.Bank{Sprites: make([]fdicon.Sprite, n)}
	for i := range b.Sprites {
		b.Sprites[i] = solid(v)
	}
	return b
}

func TestComposeFramePreservesNativeLayerOrder(t *testing.T) {
	cache := &fdicon.NativeSelectorCache{}
	if _, err := cache.SlotFor(0); err != nil {
		t.Fatal(err)
	}
	foreground := bank(12, 0)
	foreground.Sprites[1] = solid(4) // tile 0 + foreground index-one rule
	work, vga := make([]byte, 456*300), make([]byte, 320*192)
	cells := make([]fdicon.NativeTerrainCell, 13*8)
	for i := range cells {
		cells[i].BlitMode = 0xff
	}
	in := FrameInput{
		TerrainBank: bank(12, 1), RangeBank: bank(20, 2), UnitBank: bank(12, 3), ForegroundBank: foreground,
		SelectorCache: cache, Cells: cells, Controls: []byte{0x80, 0, 0, 0}, LUT: make([]byte, 256), MapWidth: 13,
		RangeMode: 1, Units: []fdicon.NativeUnitLayerEntry{{X: 0, Y: 0, Slot: 0}}, ForegroundUnits: []fdicon.NativeForegroundLayerEntry{{X: 0, Y: 0}},
	}
	if err := ComposeFrame(work, vga, in, func(frame []byte) error {
		off := workBase
		if frame[off] != 4 { // terrain -> range -> unit -> foreground
			t.Fatalf("pre-HUD pixel=%d, want foreground 4", frame[off])
		}
		frame[off] = 5
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if vga[0] != 5 {
		t.Fatalf("viewport pixel=%d, want HUD 5", vga[0])
	}
}

func TestComposeFrameRejectsMissingHUDBeforeMutation(t *testing.T) {
	work, vga := make([]byte, 456*300), make([]byte, 320*192)
	beforeWork, beforeVGA := append([]byte(nil), work...), append([]byte(nil), vga...)
	if err := ComposeFrame(work, vga, FrameInput{}, nil); err == nil {
		t.Fatal("incomplete input accepted")
	}
	if string(work) != string(beforeWork) {
		t.Fatal("rejected input mutated work buffer")
	}
	if string(vga) != string(beforeVGA) {
		t.Fatal("rejected input mutated VGA buffer")
	}
}
