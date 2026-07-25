package fdicon

import (
	"os"
	"testing"
)

func TestParseAndBlitPreserveTransparentDitherAndPaletteBand(t *testing.T) {
	// 24 rows: first is run/dither/transparent; remaining rows are transparent.
	body := []byte{0x00, 7, 0x40, 9, 0xd4}
	for i := 1; i < NativeSize; i++ {
		body = append(body, 0xd7)
	}
	raw := make([]byte, 10+len(body))
	raw[0], raw[2], raw[4] = 24, 24, 1
	raw[6] = 10
	copy(raw[10:], body)
	b, err := Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	dst := make([]byte, 32*24)
	for i := range dst {
		dst[i] = 1
	}
	if err := b.Sprites[0].BlitAt(dst, 32, 0, 0); err != nil {
		t.Fatal(err)
	}
	if got := dst[:6]; got[0] != 7 || got[1] != 1 || got[2] != 9 || got[3] != 1 || got[4] != 1 {
		t.Fatalf("pixels=%v", got)
	}
	if err := b.Sprites[0].BlitPaletteBand(dst, 32, 0, 0); err != nil {
		t.Fatal(err)
	}
	if got := dst[:6]; got[0] != 0x1f || got[1] != 1 || got[2] != 0x19 || got[3] != 1 || got[4] != 1 {
		t.Fatalf("band pixels=%v", got)
	}
	for i := range dst {
		dst[i] = 1
	}
	if err := b.Sprites[0].BlitForNativeFlags(dst, 32, 0, 0, 0x80); err != nil {
		t.Fatal(err)
	}
	if got := dst[0]; got != 0x1f {
		t.Fatalf("acted flag used raw path: %d", got)
	}
}

func TestDecodeOriginalFDICON(t *testing.T) {
	const path = "../../../org_game/炎龍騎士團/FLAME2/FDICON.B24"
	b, err := DecodeFile(path)
	if os.IsNotExist(err) {
		t.Skip("player-provided FDICON.B24 is absent")
	}
	if err != nil {
		t.Fatal(err)
	}
	if len(b.Sprites) != 1680 || len(b.Sprites[0].Pixels) != NativeSize*NativeSize {
		t.Fatalf("bank=%#v", b)
	}
	if got, err := b.SpriteFor(4, 2, 1); err != nil || len(got.Pixels) != NativeSize*NativeSize {
		t.Fatalf("native group×12+pose×3+frame selector: sprite=%#v err=%v", got, err)
	}
	if _, err := b.SpriteFor(4, 4, 0); err == nil {
		t.Fatal("out-of-range native pose was accepted")
	}
}

func TestNativeFrameIndexMatches127E0(t *testing.T) {
	cases := []struct {
		motion             int
		force              bool
		idle, moving, want int
	}{
		{0, false, 2, 0, 2}, {0, false, 3, 2, 1}, {1, false, 2, 3, 1}, {7, false, 0, 2, 2}, {1, true, 2, 2, 0},
	}
	for _, tc := range cases {
		got, err := NativeFrameIndex(tc.motion, tc.force, tc.idle, tc.moving)
		if err != nil || got != tc.want {
			t.Fatalf("%+v got=%d err=%v", tc, got, err)
		}
	}
	if _, err := NativeFrameIndex(0, false, 4, 0); err == nil {
		t.Fatal("invalid cycle accepted")
	}
}
