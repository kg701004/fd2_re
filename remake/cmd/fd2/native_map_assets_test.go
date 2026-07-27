package main

import (
	"image/color"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
)

func TestNativeMapAssetsRequireRangeOverlayBank(t *testing.T) {
	a := &nativeMapAssets{
		Terrain: &fdicon.Bank{}, Units: &fdicon.Bank{},
		Controls: []byte{0}, LUTs: make([][]byte, 10),
		Palette: make(color.Palette, 256),
	}
	if nativeMapAssetsAvailable(a) {
		t.Fatal("accepted native map bundle without FDOTHER #1 range bank")
	}
	a.Range = &fdicon.Bank{}
	if !nativeMapAssetsAvailable(a) {
		t.Fatal("complete native map bundle rejected")
	}
}
