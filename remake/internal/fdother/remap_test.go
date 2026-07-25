package fdother

import "testing"

func TestApplyRadialLUTRemapUsesStrictRadiusAndInPlaceLUT(t *testing.T) {
	dst := make([]byte, 10*10)
	for i := range dst {
		dst[i] = byte(i % 10)
	}
	lut := make([]byte, 256)
	for i := range lut {
		lut[i] = byte((i + 20) & 0xff)
	}
	spec := RadialLUTRemap{CenterX: 5, CenterY: 5, Radius: 4, Scale: 10, StartY: 0, EndY: 10, ClipWidth: 10}
	if err := ApplyRadialLUTRemap(dst, 10, lut, spec); err != nil {
		t.Fatal(err)
	}
	// dy=4 is the native strict boundary and is not mapped.
	if got := dst[1*10+5]; got != 5 {
		t.Fatalf("radius boundary changed: got %d want 5", got)
	}
	// At dy=3 the native span is trunc(sqrt(7)*10/10)=2: x=3..6.
	for x := 0; x < 10; x++ {
		got := dst[2*10+x]
		want := byte(x)
		if x >= 3 && x < 7 {
			want += 20
		}
		if got != want {
			t.Fatalf("dy=3 x=%d: got %d want %d", x, got, want)
		}
	}
	// At the centre the interval is x=1..8 (right edge exclusive).
	for x := 0; x < 10; x++ {
		got := dst[5*10+x]
		want := byte(x)
		if x >= 1 && x < 9 {
			want += 20
		}
		if got != want {
			t.Fatalf("center x=%d: got %d want %d", x, got, want)
		}
	}
}

func TestApplyRadialLUTRemapClipsToVisibleWidth(t *testing.T) {
	dst := make([]byte, 8*4)
	for i := range dst {
		dst[i] = byte(i)
	}
	lut := make([]byte, 256)
	for i := range lut {
		lut[i] = byte(255 - i)
	}
	spec := RadialLUTRemap{CenterX: 1, CenterY: 2, Radius: 3, Scale: 10, StartY: 0, EndY: 4, ClipWidth: 6}
	if err := ApplyRadialLUTRemap(dst, 8, lut, spec); err != nil {
		t.Fatal(err)
	}
	// The center-row span is three, clipped from [-2,4) to [0,4). Bytes
	// beyond ClipWidth stay untouched even though the backing stride is wider.
	for x := 0; x < 8; x++ {
		got := dst[2*8+x]
		want := byte(2*8 + x)
		if x < 4 {
			want = 255 - want
		}
		if got != want {
			t.Fatalf("clip x=%d: got %d want %d", x, got, want)
		}
	}
}

func TestApplyRadialLUTRemapRejectsIncompleteABI(t *testing.T) {
	if err := ApplyRadialLUTRemap(make([]byte, 16), 4, make([]byte, 255), RadialLUTRemap{CenterX: 1, CenterY: 1, Radius: 1, Scale: 16, EndY: 4, ClipWidth: 4}); err == nil {
		t.Fatal("short LUT was accepted")
	}
	if err := ApplyRadialLUTRemap(make([]byte, 16), 4, make([]byte, 256), RadialLUTRemap{CenterX: 4, CenterY: 1, Radius: 1, Scale: 16, EndY: 4, ClipWidth: 4}); err == nil {
		t.Fatal("out-of-clip center was accepted")
	}
	if err := ApplyRadialLUTRemap(make([]byte, 16), 4, make([]byte, 256), RadialLUTRemap{CenterX: 1, CenterY: 1, Radius: 0x8000, Scale: 16, EndY: 4, ClipWidth: 4}); err == nil {
		t.Fatal("overflowing radius was accepted")
	}
}
