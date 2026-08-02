package fdother

import (
	"bytes"
	"testing"
)

func TestParseVGAPalettePreservesSixBitScaleAsOpaqueVGA(t *testing.T) {
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
	if alpha != 0xffff {
		t.Fatalf("VGA index-zero alpha=%#x", alpha)
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
	_, _, _, rawAlpha := palette[0].RGBA()
	_, _, _, cellAlpha := im.Palette[0].RGBA()
	if rawAlpha != 0xffff || cellAlpha != 0 {
		t.Fatalf("palette alpha leaked across codec boundary: VGA=%#x cell=%#x", rawAlpha, cellAlpha)
	}
}

func TestApplyVGAPaletteDeltaUsesImmutableBaselineInclusiveAndAtomic(t *testing.T) {
	baseline := make([]byte, 256*3)
	baseline[3], baseline[4], baseline[5] = 1, 62, 63
	dac := bytes.Repeat([]byte{9}, 256*3)
	if err := ApplyVGAPaletteDelta(dac, baseline, 1, 1, 4); err != nil {
		t.Fatal(err)
	}
	if got := dac[3:9]; !bytes.Equal(got, []byte{5, 63, 63, 9, 9, 9}) {
		t.Fatalf("first delta=%v", got)
	}
	if err := ApplyVGAPaletteDelta(dac, baseline, 1, 1, 2); err != nil {
		t.Fatal(err)
	}
	if got := dac[3:9]; !bytes.Equal(got, []byte{3, 63, 63, 9, 9, 9}) {
		t.Fatalf("baseline-derived second delta=%v", got)
	}
	before := append([]byte(nil), dac...)
	if err := ApplyVGAPaletteDelta(dac, baseline, 2, 1, 1); err == nil {
		t.Fatal("invalid range accepted")
	}
	if !bytes.Equal(dac, before) {
		t.Fatal("rejected delta mutated DAC")
	}
}

func TestApplyVGAPaletteDeltaPreservesByteSizedWhiteFlash(t *testing.T) {
	baseline := make([]byte, 256*3)
	baseline[0], baseline[1], baseline[2] = 0, 1, 63
	dac := bytes.Repeat([]byte{7}, 256*3)
	if err := ApplyVGAPaletteDelta(dac, baseline, 0, 255, 255); err != nil {
		t.Fatal(err)
	}
	for i, component := range dac {
		if component != 63 {
			t.Fatalf("white flash component %d=%d", i, component)
		}
	}
	before := append([]byte(nil), dac...)
	if err := ApplyVGAPaletteDelta(dac, baseline, 0, 255, 256); err == nil {
		t.Fatal("delta wider than the recovered byte argument was accepted")
	}
	if !bytes.Equal(dac, before) {
		t.Fatal("rejected byte-sized delta boundary mutated DAC")
	}
}

func TestApplyVGAPaletteSubtractionUsesImmutableBaselineInclusiveAndAtomic(t *testing.T) {
	baseline := make([]byte, 256*3)
	baseline[3], baseline[4], baseline[5] = 1, 62, 63
	dac := bytes.Repeat([]byte{9}, 256*3)
	if err := ApplyVGAPaletteSubtraction(dac, baseline, 1, 1, 4); err != nil {
		t.Fatal(err)
	}
	if got := dac[3:9]; !bytes.Equal(got, []byte{0, 58, 59, 9, 9, 9}) {
		t.Fatalf("first subtraction=%v", got)
	}
	if err := ApplyVGAPaletteSubtraction(dac, baseline, 1, 1, 2); err != nil {
		t.Fatal(err)
	}
	if got := dac[3:9]; !bytes.Equal(got, []byte{0, 60, 61, 9, 9, 9}) {
		t.Fatalf("baseline-derived second subtraction=%v", got)
	}
	before := append([]byte(nil), dac...)
	if err := ApplyVGAPaletteSubtraction(dac, baseline, 2, 1, 1); err == nil {
		t.Fatal("invalid subtraction range accepted")
	}
	if !bytes.Equal(dac, before) {
		t.Fatal("rejected subtraction mutated DAC")
	}
}
