package fdother

import (
	"os"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
)

func TestNativeRangeOverlayPlacementsMatch122DC(t *testing.T) {
	tests := []struct {
		mode int
		want []NativeRangeOverlayPlacement
	}{
		{1, []NativeRangeOverlayPlacement{{10, 20, 0}}},
		{2, []NativeRangeOverlayPlacement{{10, 20, 1}}},
		{3, []NativeRangeOverlayPlacement{{10, 20, 14}, {10, 19, 2}, {9, 20, 3}, {11, 20, 4}, {10, 21, 5}}},
		{4, []NativeRangeOverlayPlacement{{10, 20, 1}, {10, 18, 2}, {8, 20, 3}, {12, 20, 4}, {10, 22, 5}, {9, 19, 6}, {11, 19, 7}, {9, 21, 8}, {11, 21, 9}, {10, 19, 10}, {9, 20, 11}, {11, 20, 12}, {10, 21, 13}}},
		{5, []NativeRangeOverlayPlacement{{10, 20, 1}, {10, 17, 2}, {7, 20, 3}, {13, 20, 4}, {10, 23, 5}, {9, 18, 6}, {8, 19, 6}, {11, 18, 7}, {8, 22, 7}, {11, 22, 8}, {11, 18, 8}, {12, 22, 9}, {11, 22, 9}, {10, 18, 10}, {8, 20, 11}, {12, 20, 12}, {10, 22, 13}, {9, 19, 15}, {11, 19, 16}, {9, 21, 17}, {11, 21, 18}}},
	}
	for _, test := range tests {
		got, err := NativeRangeOverlayPlacements(test.mode, 10, 20)
		if err != nil {
			t.Fatalf("mode %d: %v", test.mode, err)
		}
		if len(got) != len(test.want) {
			t.Fatalf("mode %d: got %d calls, want %d", test.mode, len(got), len(test.want))
		}
		for i := range test.want {
			if got[i] != test.want[i] {
				t.Fatalf("mode %d call %d: got %#v want %#v", test.mode, i, got[i], test.want[i])
			}
		}
	}
}

func TestNativeRangeOverlayRejectsMode6AndInvalid(t *testing.T) {
	for _, mode := range []int{0, 6, 7} {
		if _, err := NativeRangeOverlayPlacements(mode, 0, 0); err == nil {
			t.Fatalf("mode %d accepted", mode)
		}
	}
}

func TestNativeRangeOverlayMode6ByteAddress(t *testing.T) {
	got, err := NativeRangeOverlayMode6ByteAddress(17, 3, 2)
	if err != nil || got != 4*(3+2*17)+7 {
		t.Fatalf("got %d, %v", got, err)
	}
	if _, err := NativeRangeOverlayMode6ByteAddress(0, 3, 2); err == nil {
		t.Fatal("zero width accepted")
	}
}

func TestNativeRangeOverlayBankAndBlit(t *testing.T) {
	const path = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(path); os.IsNotExist(err) {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	bank, err := DecodeNativeRangeOverlayBank(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(bank.Sprites) != 20 {
		t.Fatalf("FDOTHER#1 descriptor count=%d, want 20", len(bank.Sprites))
	}
	for i, sprite := range bank.Sprites {
		if len(sprite.Pixels) != fdicon.NativeSize*fdicon.NativeSize {
			t.Fatalf("FDOTHER#1 descriptor %d has %d pixels", i, len(sprite.Pixels))
		}
	}
	dst := make([]byte, nativeRangeOverlayStride*300)
	if err := BlitNativeRangeOverlay(bank, dst, 10, 20, 13, 8, 4, 10, 20); err != nil {
		t.Fatal(err)
	}
	before := append([]byte(nil), dst...)
	if err := BlitNativeRangeOverlay(bank, dst, 10, 20, 13, 8, 6, 10, 20); err == nil {
		t.Fatal("mode 6 was accepted as drawable")
	}
	if string(dst) != string(before) {
		t.Fatal("rejected mode mutated framebuffer")
	}
}

func TestBlitNativeRangeOverlayPreflightsDestination(t *testing.T) {
	bank := &fdicon.Bank{Sprites: make([]fdicon.Sprite, 20)}
	for i := range bank.Sprites {
		bank.Sprites[i] = fdicon.Sprite{Pixels: make([]byte, 24*24), Mask: make([]byte, 24*24), RemapMask: make([]byte, 24*24)}
	}
	dst := make([]byte, nativeRangeOverlayStride*80)
	before := append([]byte(nil), dst...)
	if err := BlitNativeRangeOverlay(bank, dst, 0, 0, 13, 8, 1, 0, 0); err == nil {
		t.Fatal("undersized framebuffer accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("failed preflight mutated framebuffer")
	}
}
