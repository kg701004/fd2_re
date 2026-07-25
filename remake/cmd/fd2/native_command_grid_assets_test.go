package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestNativeCommandGridPlayerAssetGate(t *testing.T) {
	datPath := filepath.Clean("../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT")
	if _, err := os.Stat(datPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", datPath)
	if palette := loadNativeUIPalette(); len(palette) != 256 {
		t.Fatalf("native UI palette entries=%d, want 256", len(palette))
	}
	if labels := loadNativeCommandLabels(); labels[0] == "" {
		t.Fatal("native command label 0 is unavailable")
	}
	if font := loadFont(); font == nil {
		t.Fatal("native command grid font is unavailable")
	}
}
