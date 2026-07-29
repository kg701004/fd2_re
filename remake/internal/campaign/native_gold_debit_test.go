package campaign

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func nativeGoldTestStrip() fdother.RawCell {
	pixels := make([]byte, 6*99)
	for row := 0; row < 99; row++ {
		for col := 0; col < 6; col++ {
			pixels[row*6+col] = byte(row + 1)
		}
	}
	return fdother.RawCell{Width: 6, Height: 99, Pixels: pixels}
}

func TestComposeNativeGoldDebitFramesPreservesOdometerSchedule(t *testing.T) {
	base := make([]byte, NativeShopWidth*NativeShopHeight)
	frames, next, err := ComposeNativeGoldDebitFrames(
		base, nativeGoldTestStrip(), 1000, 50,
	)
	if err != nil {
		t.Fatal(err)
	}
	// 00001000 -> 00000950: the slowest digit descends five values, with
	// nine vertical-strip phases per value.
	if next != 950 || len(frames) != 45 {
		t.Fatalf("next=%d frames=%d, want 950/45", next, len(frames))
	}
	// Hundreds and tens both roll on the first pass. The first phase begins
	// at row digit*9+8; the ninth finishes at the stable digit row.
	if got := frames[0][NativeShopGoldOffset+4*6]; got != 9 {
		t.Fatalf("first hundreds roll row=%d, want strip row8 value9", got)
	}
	if got := frames[8][NativeShopGoldOffset+4*6]; got != 1 {
		t.Fatalf("final hundreds row=%d, want strip row0 value1", got)
	}
	if got := frames[8][NativeShopGoldOffset+5*6]; got != 82 {
		t.Fatalf("final tens row=%d, want strip row81 value82", got)
	}
	if got := frames[0][NativeShopGoldOffset+5*6]; got != 90 {
		t.Fatalf("wrapped tens first row=%d, want strip row89 value90", got)
	}
	if got := frames[9][NativeShopGoldOffset+6*6]; got != 81 {
		t.Fatalf("second roll first row=%d, want strip row80 value81", got)
	}
	// The units digit never differs and must preserve its background.
	if got := frames[44][NativeShopGoldOffset+7*6]; got != 0 {
		t.Fatalf("unchanged units pixel=%d, want preserved 0", got)
	}
	for index, got := range frames {
		if got[NativeShopGoldOffset-1] != 0 ||
			got[NativeShopGoldOffset+8*6] != 0 {
			t.Fatalf("frame%d wrote outside eight digit windows", index)
		}
	}
	cascade, next, err := ComposeNativeGoldDebitFrames(
		base, nativeGoldTestStrip(), 10_000_000, 1,
	)
	if err != nil || next != 9_999_999 || len(cascade) != 9 {
		t.Fatalf(
			"borrow cascade = frames%d next%d err%v, want 9/9999999",
			len(cascade), next, err,
		)
	}
}

func TestComposeNativeGoldDebitFramesRejectsInvalidState(t *testing.T) {
	base := make([]byte, NativeShopWidth*NativeShopHeight)
	strip := nativeGoldTestStrip()
	for _, tc := range []struct {
		base   []byte
		strip  fdother.RawCell
		old    int
		amount int
	}{
		{base[:1], strip, 100, 1},
		{base, fdother.RawCell{Width: 6, Height: 98}, 100, 1},
		{base, strip, -1, 1},
		{base, strip, 100, 101},
		{base, strip, 100_000_000, 1},
	} {
		if _, _, err := ComposeNativeGoldDebitFrames(
			tc.base, tc.strip, tc.old, tc.amount,
		); err == nil {
			t.Fatalf("invalid state accepted: %#v", tc)
		}
	}
	frames, next, err := ComposeNativeGoldDebitFrames(base, strip, 100, 0)
	if err != nil || next != 100 || len(frames) != 0 {
		t.Fatalf("zero debit = frames%d next%d err%v", len(frames), next, err)
	}
}
