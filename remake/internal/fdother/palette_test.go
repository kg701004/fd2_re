package fdother

import "testing"

func TestParseVGAPalettePreservesSixBitScaleAndTransparency(t *testing.T) {
	raw := make([]byte, 256*3)
	raw[3], raw[4], raw[5] = 63, 32, 1
	palette, err := ParseVGAPalette(raw)
	if err != nil {
		t.Fatal(err)
	}
	if got := palette[0].(interface {
		RGBA() (uint32, uint32, uint32, uint32)
	}); got == nil {
		t.Fatal("palette index zero missing")
	}
	_, _, _, alpha := palette[0].RGBA()
	if alpha != 0 {
		t.Fatalf("transparent index alpha=%#x", alpha)
	}
	r, g, b, a := palette[1].RGBA()
	if r != 0xffff || g != 0x8282 || b != 0x0404 || a != 0xffff {
		t.Fatalf("palette[1]=%#x,%#x,%#x,%#x", r, g, b, a)
	}
}

func TestRawCellPalettedPreservesZeroIndex(t *testing.T) {
	palette, err := ParseVGAPalette(make([]byte, 256*3))
	if err != nil {
		t.Fatal(err)
	}
	im, err := (RawCell{Width: 2, Height: 1, Pixels: []byte{0, 7}}).Paletted(palette)
	if err != nil {
		t.Fatal(err)
	}
	if got := im.ColorIndexAt(0, 0); got != 0 {
		t.Fatalf("zero index=%d", got)
	}
	if got := im.ColorIndexAt(1, 0); got != 7 {
		t.Fatalf("opaque index=%d", got)
	}
}
