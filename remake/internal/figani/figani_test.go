package figani

import (
	"os"
	"testing"
)

func TestParsePreservesTransparentAndDitherPixels(t *testing.T) {
	// One 4x1 frame: run(7), dither(9), then transparent skip.
	raw := []byte{1, 0, 0, 0, 0x7e, 0, 12, 0, 12, 0, 0, 0, 2, 0, 3, 0, 0, 0, 2, 0, 0, 4, 0, 1, 0, 0x00, 7, 0x40, 9, 0xc0}
	a, err := Parse(raw)
	if err != nil {
		t.Fatal(err)
	}
	f := a.Frames[0]
	if f.X != 2 || f.Y != 3 || f.Width != 4 || f.Height != 1 || f.Delay != 2 {
		t.Fatalf("frame=%#v", f)
	}
	if a.HeaderByte4 != 0x7e {
		t.Fatalf("HeaderByte4=%#x, want 0x7e", a.HeaderByte4)
	}
	dst := make([]byte, 50)
	for i := range dst {
		dst[i] = 1
	}
	if err := f.BlitAt(dst, 10); err != nil {
		t.Fatal(err)
	}
	if got := dst[32:36]; got[0] != 7 || got[1] != 1 || got[2] != 9 || got[3] != 1 {
		t.Fatalf("blit=%v", got)
	}
}

func TestDecodeOriginalFIGANIResource(t *testing.T) {
	const path = "../../../org_game/炎龍騎士團/FLAME2/FIGANI.DAT"
	a, err := DecodeResource(path, 13)
	if os.IsNotExist(err) {
		t.Skip("player-provided FIGANI.DAT is absent")
	}
	if err != nil {
		t.Fatal(err)
	}
	if len(a.Frames) == 0 || a.Frames[0].Width <= 0 || a.Frames[0].Height <= 0 || len(a.Frames[0].Pixels) != a.Frames[0].Width*a.Frames[0].Height {
		t.Fatalf("decoded resource 13 = %#v", a)
	}
}

func TestDecodeOriginalPlayerClass19HeaderFlags(t *testing.T) {
	const path = "../../../org_game/炎龍騎士團/FLAME2/FIGANI.DAT"
	// Player-reachable class-19 sources use visual groups 4..7 (optional
	// class change) or 20 (Sara's initial class). 0x2b659 receives group*3+1.
	for resource, want := range map[int]byte{13: 2, 16: 2, 19: 2, 22: 5, 61: 5} {
		a, err := DecodeResource(path, resource)
		if os.IsNotExist(err) {
			t.Skip("player-provided FIGANI.DAT is absent")
		}
		if err != nil {
			t.Fatalf("resource %d: %v", resource, err)
		}
		if a.HeaderByte4 != want {
			t.Errorf("resource %d HeaderByte4=%d, want %d", resource, a.HeaderByte4, want)
		}
	}
}

func TestFrameBlitAtBaseShiftsNativeWorkSurface(t *testing.T) {
	f := Frame{X: 2, Y: 3, Width: 1, Height: 1, Pixels: []byte{9}, Mask: []byte{1}}
	dst := make([]byte, 640*5)
	if err := f.BlitAtBase(dst, 640, 80); err != nil {
		t.Fatal(err)
	}
	if got := dst[80+3*640+2]; got != 9 {
		t.Fatalf("shifted pixel=%d", got)
	}
}
