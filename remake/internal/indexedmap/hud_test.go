package indexedmap

import (
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
