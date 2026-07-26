package indexedmap

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
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

func TestComposeNativeFrameBindsRecoveredHUDInsteadOfCallback(t *testing.T) {
	// The native work pointer is 0x8088, so the 192-row viewport reaches
	// through row 319 even though the HUD itself occupies the final 200 rows.
	work := make([]byte, workStride*320)
	vga := make([]byte, viewWidth*viewHeight)
	terrain := bank(2, 0)
	terrain.Sprites[0] = solid(1)
	terrain.Sprites[1] = solid(0x66)
	rangeBank := bank(20, 0)
	units := bank(12, 0)
	units.Sprites[0] = solid(2)
	units.Sprites[1] = solid(0x77)
	cache := &fdicon.NativeSelectorCache{}
	if _, err := cache.SlotFor(0); err != nil {
		t.Fatal(err)
	}
	cells := make([]fdicon.NativeTerrainCell, 13*8)
	for i := range cells {
		cells[i].BlitMode = 0xff
	}
	in := NativeFrameInput{
		Frame: FrameInput{
			TerrainBank: terrain, RangeBank: rangeBank, UnitBank: units, ForegroundBank: terrain, SelectorCache: cache,
			Cells: cells, Controls: []byte{0, 2, 0, 0, 0, 2, 0, 0}, MapWidth: 13,
			RangeMode: 1, Units: []fdicon.NativeUnitLayerEntry{{X: 0, Y: 0, Slot: 0}},
		},
		HUD: NativeMapHUDInput{DisplayGateA: true, DisplayGateB: true, AnchorX: 136, TerrainDescriptor: 1, TerrainControl: 2,
			OptionalUnit: &NativeMapHUDOptionalUnit{SelectorSlot: 0, RawState: 3, Current: 7, Maximum: 8}},
		Frames: hudFrames(), HUDTerrain: terrain, HUDUnits: units, HUDCache: cache,
	}
	if err := ComposeNativeFrame(work, vga, in); err != nil {
		t.Fatal(err)
	}
	layout, _ := fdicon.NativeMapHUDLayoutFor(136, workStride)
	if work[layout.Frame] != 0x5a || work[layout.Terrain] != 0x66 || work[layout.Unit] != 0x77 || work[layout.HP] != 0x70 {
		t.Fatalf("native HUD missing from work: %#x/%#x/%#x/%#x", work[layout.Frame], work[layout.Terrain], work[layout.Unit], work[layout.HP])
	}
	// The viewport copy starts at workBase=(x=72,y=72); the HUD panel at
	// anchor 136 therefore lands at viewport (x=64,y=85).
	if got := vga[85*viewWidth+64]; got != 0x5a {
		t.Fatalf("native HUD did not reach viewport: %#x", got)
	}
}

func TestComposeNativeTransitionFramePreservesNativeLayerOrder(t *testing.T) {
	work := make([]byte, workStride*320)
	vga := make([]byte, viewWidth*viewHeight)
	cells := make([]fdicon.NativeTerrainCell, 13*8)
	for i := range cells {
		cells[i].BlitMode = 0xff
	}
	cache := &fdicon.NativeSelectorCache{}
	if _, err := cache.SlotFor(0); err != nil {
		t.Fatal(err)
	}
	identity := make([]byte, 256)
	for i := range identity {
		identity[i] = byte(i)
	}
	pass, err := fdother.BuildNativeIndexedTransitionPass(6, 6, 10, 0, 192)
	if err != nil {
		t.Fatal(err)
	}
	in := NativeTransitionFrameInput{
		TerrainBank: bank(12, 7), UnitBank: bank(12, 0), ForegroundBank: bank(12, 0), SelectorCache: cache,
		Cells: cells, Controls: []byte{0, 0, 0, 0}, TerrainLUT: identity, MapWidth: 13,
	}
	if err := ComposeNativeTransitionFrame(work, vga, in, pass, identity); err != nil {
		t.Fatal(err)
	}
	if got := vga[0]; got != 7 {
		t.Fatalf("transition viewport first pixel=%d want terrain 7", got)
	}
}

func TestComposeNativeTransitionFrameRejectsMissingRawInputAtomically(t *testing.T) {
	work := make([]byte, workStride*320)
	vga := make([]byte, viewWidth*viewHeight)
	work[0], vga[0] = 9, 8
	pass, err := fdother.BuildNativeIndexedTransitionPass(6, 6, 10, 0, 192)
	if err != nil {
		t.Fatal(err)
	}
	if err := ComposeNativeTransitionFrame(work, vga, NativeTransitionFrameInput{}, pass, nil); err == nil {
		t.Fatal("missing transition input accepted")
	}
	if work[0] != 9 || vga[0] != 8 {
		t.Fatal("rejected transition mutated caller buffers")
	}
}

func TestBuildNativeTerrainCellsRequiresExporterArrays(t *testing.T) {
	cells, err := BuildNativeTerrainCells([]int{1, 2}, []byte{0xff, 0x00})
	if err != nil || len(cells) != 2 || cells[0].Tile != 1 || cells[1].BlitMode != 0 {
		t.Fatalf("cells=%#v err=%v", cells, err)
	}
	for _, tc := range []struct {
		tiles []int
		modes []byte
	}{
		{[]int{1}, nil},
		{[]int{0x400}, []byte{0}},
	} {
		if _, err := BuildNativeTerrainCells(tc.tiles, tc.modes); err == nil {
			t.Fatalf("accepted incomplete/invalid arrays: %#v", tc)
		}
	}
}
