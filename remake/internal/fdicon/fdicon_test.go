package fdicon

import (
	"os"
	"testing"
)

func TestParseAndBlitPreserveTransparentDitherAndLUT(t *testing.T) {
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
	lut := make([]byte, 256)
	for i := range lut {
		lut[i] = byte(i + 10)
	}
	dst := make([]byte, 32*24)
	for i := range dst {
		dst[i] = 1
	}
	if err := b.Sprites[0].BlitAt(dst, 32, 0, 0, lut); err != nil {
		t.Fatal(err)
	}
	if got := dst[:6]; got[0] != 17 || got[1] != 1 || got[2] != 19 || got[3] != 1 || got[4] != 1 {
		t.Fatalf("pixels=%v", got)
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
