package fdicon

import "testing"

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
