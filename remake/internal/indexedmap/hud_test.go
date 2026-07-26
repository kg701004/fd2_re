package indexedmap

import (
	"errors"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestBlitNativeMapHUDPanelGatesAndOrigin(t *testing.T) {
	entries := make([]fdother.LMI1Entry, nativeMapHUDPanelEntry+1)
	entries[nativeMapHUDPanelEntry] = fdother.LMI1Entry{Width: 69, Height: 34, Pixels: make([]byte, 69*34)}
	entries[nativeMapHUDPanelEntry].Pixels[0] = 0x5a
	dst := make([]byte, fdicon.NativeMapStride*200)
	if err := BlitNativeMapHUDPanel(entries, dst, true, false, 1); err != nil {
		t.Fatal(err)
	}
	layout, _ := fdicon.NativeMapHUDLayoutFor(1, fdicon.NativeMapStride)
	if dst[layout.Frame] != 0 {
		t.Fatal("closed display gate drew panel")
	}
	if err := BlitNativeMapHUDPanel(entries, dst, true, true, 1); err != nil {
		t.Fatal(err)
	}
	if dst[layout.Frame] != 0x5a {
		t.Fatalf("panel byte=%#x, want %#x", dst[layout.Frame], 0x5a)
	}
}

func TestBlitNativeMapHUDPanelRejectsInvalidEntryBeforeWrite(t *testing.T) {
	entries := make([]fdother.LMI1Entry, nativeMapHUDPanelEntry+1)
	entries[nativeMapHUDPanelEntry] = fdother.LMI1Entry{Width: 1, Height: 1, Pixels: []byte{7}}
	dst, before := make([]byte, fdicon.NativeMapStride*200), make([]byte, fdicon.NativeMapStride*200)
	if err := BlitNativeMapHUDPanel(entries, dst, true, true, 1); err == nil {
		t.Fatal("wrong panel geometry accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("rejected panel mutated destination")
	}
}

func TestBlitNativeMapHUDSignedNumberSelectsSignAndAbsoluteValue(t *testing.T) {
	entries := make([]fdother.LMI1Entry, nativeMapHUDNegativeSignEntry+1)
	entries[nativeMapHUDPositiveSignEntry] = fdother.LMI1Entry{Width: 6, Height: 7, Pixels: make([]byte, 42)}
	entries[nativeMapHUDNegativeSignEntry] = fdother.LMI1Entry{Width: 6, Height: 5, Pixels: make([]byte, 30)}
	entries[nativeMapHUDPositiveSignEntry].Pixels[0] = 0x31
	entries[nativeMapHUDNegativeSignEntry].Pixels[0] = 0x42
	dst := make([]byte, fdicon.NativeMapStride*30)
	calledOrigin, calledAbsolute := -1, -1
	draw := func(frame []byte, origin, absolute int) error {
		calledOrigin, calledAbsolute = origin, absolute
		frame[origin] = 0x5a
		return nil
	}
	origin := fdicon.NativeMapStride + 10
	if err := BlitNativeMapHUDSignedNumber(entries, dst, origin, 12, draw); err != nil {
		t.Fatal(err)
	}
	if dst[origin] != 0x31 || dst[origin+8] != 0x5a || calledOrigin != origin+8 || calledAbsolute != 12 {
		t.Fatalf("positive sign/digits mismatch: sign=%#x origin=%d absolute=%d", dst[origin], calledOrigin, calledAbsolute)
	}
	if err := BlitNativeMapHUDSignedNumber(entries, dst, origin, -9, draw); err != nil {
		t.Fatal(err)
	}
	if dst[origin] != 0x42 || calledAbsolute != 9 {
		t.Fatalf("negative sign/absolute mismatch: sign=%#x absolute=%d", dst[origin], calledAbsolute)
	}
}

func TestBlitNativeMapHUDSignedNumberIsAtomicOnDigitFailure(t *testing.T) {
	entries := make([]fdother.LMI1Entry, nativeMapHUDNegativeSignEntry+1)
	entries[nativeMapHUDPositiveSignEntry] = fdother.LMI1Entry{Width: 6, Height: 7, Pixels: make([]byte, 42)}
	entries[nativeMapHUDNegativeSignEntry] = fdother.LMI1Entry{Width: 6, Height: 5, Pixels: make([]byte, 30)}
	dst := make([]byte, fdicon.NativeMapStride*20)
	before := append([]byte(nil), dst...)
	if err := BlitNativeMapHUDSignedNumber(entries, dst, 1, 1, func([]byte, int, int) error { return errors.New("digits") }); err == nil {
		t.Fatal("digit failure accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("digit failure partially drew sign")
	}
}
