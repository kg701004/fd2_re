package fdicon

import "testing"

func TestNativeTerrainCursorInfoForCellMatches12E38(t *testing.T) {
	controls := make([]byte, 0x12*4)
	copy(controls[0x11*4:], []byte{0x80, 0x12, 0x34, 0x56})
	got, err := NativeTerrainCursorInfoForCell(0xfc11, 0xffe5, controls)
	if err != nil {
		t.Fatal(err)
	}
	if got.Tile != 0x11 || got.EventLow != 5 || got.Control != [4]byte{0x80, 0x12, 0x34, 0x56} {
		t.Fatalf("info=%+v", got)
	}
	if _, err := NativeTerrainCursorInfoForCell(0x12, 0, controls); err == nil {
		t.Fatal("out-of-range control accepted")
	}
}

func TestNativeMapHUDUnitFrameIndexMatches1AE4D(t *testing.T) {
	for _, tc := range []struct{ group, state, want int }{{0, 0, 0}, {2, 1, 25}, {2, 2, 26}, {2, 3, 25}} {
		got, err := NativeMapHUDUnitFrameIndex(tc.group, tc.state)
		if err != nil || got != tc.want {
			t.Errorf("(%d,%d)=(%d,%v), want %d", tc.group, tc.state, got, err, tc.want)
		}
	}
	if _, err := NativeMapHUDUnitFrameIndex(0, 4); err == nil {
		t.Fatal("out-of-range raw state was accepted")
	}
}

func TestNativeForegroundRedrawEligibleMatches129ECGates(t *testing.T) {
	cases := []struct {
		name                         string
		inactive, unit7, race, class byte
		want                         bool
	}{
		{"inactive always skips", 1, 0x1c, 0, 0, false},
		{"ordinary active", 0, 0, 0, 0, true},
		{"unit plus 7 1c overrides raw gate", 0, 0x1c, 4, 0x13, true},
		{"class 13 skips", 0, 0, 0, 0x13, false},
		{"race 4 skips", 0, 0, 4, 0, false},
		{"race 5 skips", 0, 0, 5, 0, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := NativeForegroundRedrawEligible(tc.inactive != 0, tc.unit7, tc.race, tc.class)
			if got != tc.want {
				t.Fatalf("eligible=%v want=%v", got, tc.want)
			}
		})
	}
}

func TestNativeForegroundRedrawCellsMatches129EC(t *testing.T) {
	cases := []struct {
		name           string
		pose           byte
		movementOffset int
		want           []NativeCellCoordinate
	}{
		{"stationary", 0, 0, []NativeCellCoordinate{{10, 20}, {10, 19}}},
		{"down", 0, 1, []NativeCellCoordinate{{10, 20}, {10, 19}, {10, 21}}},
		{"left", 1, -1, []NativeCellCoordinate{{10, 20}, {10, 19}, {9, 20}}},
		{"up", 2, 1, []NativeCellCoordinate{{10, 20}, {10, 19}, {10, 18}}},
		{"right", 3, 1, []NativeCellCoordinate{{10, 20}, {10, 19}, {11, 20}}},
		{"native default right", 0xff, 1, []NativeCellCoordinate{{10, 20}, {10, 19}, {11, 20}}},
		{"unclipped", 1, 1, []NativeCellCoordinate{{0, 0}, {0, -1}, {-1, 0}}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			x, y := 10, 20
			if tc.name == "unclipped" {
				x, y = 0, 0
			}
			got, n := NativeForegroundRedrawCells(x, y, tc.pose, tc.movementOffset)
			if n != len(tc.want) {
				t.Fatalf("count=%d want=%d", n, len(tc.want))
			}
			for i := range tc.want {
				if got[i] != tc.want[i] {
					t.Fatalf("cell[%d]=%+v want=%+v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestNativeTerrainFrameIndexMatches11EEE(t *testing.T) {
	cases := []struct {
		flags       byte
		flip, cycle int
		want        int
	}{
		{0x00, 1, 9, 100}, {0x04, 1, 9, 101}, {0x10, 1, 9, 104}, {0x08, 1, 9, 102},
		{0x1c, 1, 9, 102}, {0x10, 0, -3, 99},
	}
	for _, tc := range cases {
		got, err := NativeTerrainFrameIndex(100, tc.flags, tc.flip, tc.cycle)
		if err != nil || got != tc.want {
			t.Fatalf("%+v got=%d err=%v", tc, got, err)
		}
	}
	if _, err := NativeTerrainFrameIndex(0x400, 0, 0, 0); err == nil {
		t.Fatal("out-of-range tile accepted")
	}
	if _, err := NativeTerrainFrameIndex(0, 0, 2, 0); err == nil {
		t.Fatal("invalid flip accepted")
	}
}

func TestNativeForegroundFrameIndexMatches12AC6(t *testing.T) {
	cases := []struct {
		flags, flip int
		want        int
		present     bool
	}{
		{0x00, 0, 0, false}, {0x80, 0, 101, true}, {0x88, 1, 103, true}, {0x88, 0, 101, true},
	}
	for _, tc := range cases {
		got, present, err := NativeForegroundFrameIndex(100, byte(tc.flags), tc.flip)
		if err != nil || got != tc.want || present != tc.present {
			t.Fatalf("%+v got=%d present=%v err=%v", tc, got, present, err)
		}
	}
	if _, _, err := NativeForegroundFrameIndex(0x400, 0x80, 0); err == nil {
		t.Fatal("out-of-range tile accepted")
	}
}

func TestBlitNativeTerrainCellSelectsRawOrLUTBranch(t *testing.T) {
	sprites := make([]Sprite, 12)
	for i := range sprites {
		sprites[i] = Sprite{Pixels: make([]byte, NativeSize*NativeSize), Mask: make([]byte, NativeSize*NativeSize), RemapMask: make([]byte, NativeSize*NativeSize)}
	}
	sprites[0].Pixels[0], sprites[0].Mask[0] = 7, 1
	sprites[1].Pixels[0], sprites[1].Mask[0] = 9, 1
	sprites[1].RemapMask[1] = 1
	b := &Bank{Sprites: sprites}
	dst := make([]byte, NativeSize*NativeSize)
	for i := range dst {
		dst[i] = 1
	}
	if err := b.BlitNativeTerrainCell(dst, NativeSize, 0, 0, 0, 0, 0xff, 0, 0, nil); err != nil {
		t.Fatal(err)
	}
	if dst[0] != 7 {
		t.Fatalf("raw branch=%d", dst[0])
	}
	lut := make([]byte, 256)
	for i := range lut {
		lut[i] = byte(i + 0x10)
	}
	for i := range dst {
		dst[i] = 1
	}
	if err := b.BlitNativeTerrainCell(dst, NativeSize, 0, 0, 0, 0x04, 0, 1, 0, lut); err != nil {
		t.Fatal(err)
	}
	if dst[0] != 0x19 || dst[1] != 0x11 {
		t.Fatalf("LUT branch=%#x,%#x", dst[0], dst[1])
	}
}

func TestBlitNativeTerrainRegionMatches11EEECellOrder(t *testing.T) {
	pixels, mask := make([]byte, NativeSize*NativeSize), make([]byte, NativeSize*NativeSize)
	pixels[0], mask[0] = 7, 1
	b := &Bank{Sprites: make([]Sprite, 12)}
	for i := range b.Sprites {
		b.Sprites[i] = Sprite{Pixels: pixels, Mask: mask, RemapMask: make([]byte, NativeSize*NativeSize)}
	}
	lut := make([]byte, 256)
	for i := range lut {
		lut[i] = byte(i + 0x10)
	}
	dst := make([]byte, NativeSize*NativeSize*2)
	if err := b.BlitNativeTerrainRegion(dst, NativeSize*2, 0, 0, 2,
		[]NativeTerrainCell{{Tile: 0, BlitMode: 0xff}, {Tile: 0, BlitMode: 0}},
		[]byte{0, 0, 0, 0}, 0, 0, 2, 1, 0, 0, lut); err != nil {
		t.Fatal(err)
	}
	if dst[0] != 7 || dst[NativeSize] != 0x17 {
		t.Fatalf("region cells=%#x,%#x", dst[0], dst[NativeSize])
	}
	if err := b.BlitNativeTerrainRegion(dst, NativeSize, 0, 0, 1, []NativeTerrainCell{{}}, nil, 0, 0, 1, 1, 0, 0, lut); err == nil {
		t.Fatal("short control table accepted")
	}
}

func TestBlitNativeForegroundCellMatches12AC6(t *testing.T) {
	b := &Bank{Sprites: make([]Sprite, 12)}
	for i := range b.Sprites {
		b.Sprites[i] = Sprite{Pixels: make([]byte, NativeSize*NativeSize), Mask: make([]byte, NativeSize*NativeSize), RemapMask: make([]byte, NativeSize*NativeSize)}
	}
	b.Sprites[1].Pixels[0], b.Sprites[1].Mask[0] = 7, 1
	b.Sprites[1].RemapMask[1] = 1
	dst := make([]byte, NativeSize*NativeSize)
	for i := range dst {
		dst[i] = 1
	}
	lut := make([]byte, 256)
	for i := range lut {
		lut[i] = byte(i + 0x10)
	}
	if err := b.BlitNativeForegroundCell(dst, NativeSize, 0, 0, 0, 0x80, 0, 0, lut); err != nil {
		t.Fatal(err)
	}
	if dst[0] != 0x17 || dst[1] != 1 {
		t.Fatalf("foreground=%#x,%#x", dst[0], dst[1])
	}
}
