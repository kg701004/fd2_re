package main

import (
	"encoding/json"
	"os"
	"strconv"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/figani"
)

// meta.json is the runtime bridge for the native 0x2935b frame-header X/Y
// contract. Verify every exported animation against the player-provided
// FIGANI archive so a stale export cannot silently change figure placement.
func TestFIGANIMetaMatchesNativeFrameHeaders(t *testing.T) {
	const archivePath = "../../../org_game/炎龍騎士團/FLAME2/FIGANI.DAT"
	if _, err := os.Stat(archivePath); err != nil {
		t.Skip("player-provided FIGANI.DAT is absent")
	}
	raw, err := os.ReadFile("../../assets/figani/meta.json")
	if err != nil {
		t.Fatal(err)
	}
	var meta map[string][][2]int
	if err := json.Unmarshal(raw, &meta); err != nil {
		t.Fatal(err)
	}
	if len(meta) == 0 {
		t.Fatal("FIGANI metadata is empty")
	}
	for key, positions := range meta {
		resource, err := strconv.Atoi(key)
		if err != nil {
			t.Fatalf("invalid FIGANI metadata key %q: %v", key, err)
		}
		animation, err := figani.DecodeResource(archivePath, resource)
		if err != nil {
			t.Fatalf("FIGANI %d: %v", resource, err)
		}
		if len(positions) != len(animation.Frames) {
			t.Fatalf("FIGANI %d meta frames=%d, native=%d", resource, len(positions), len(animation.Frames))
		}
		for i, frame := range animation.Frames {
			if got := positions[i]; got != [2]int{frame.X, frame.Y} {
				t.Fatalf("FIGANI %d frame %d meta=%v, native=(%d,%d)", resource, i, got, frame.X, frame.Y)
			}
		}
	}
}

// delays.json is the presentation bridge for native FIGANI descriptor +6.
// Keep the archive comparison separate from meta.json so a stale timing
// export cannot silently change the full-screen attack cadence.
func TestFIGANIDelaysMatchNativeFrameHeaders(t *testing.T) {
	const archivePath = "../../../org_game/炎龍騎士團/FLAME2/FIGANI.DAT"
	if _, err := os.Stat(archivePath); err != nil {
		t.Skip("player-provided FIGANI.DAT is absent")
	}
	raw, err := os.ReadFile("../../assets/figani/delays.json")
	if err != nil {
		t.Fatal(err)
	}
	var delays map[string][]int
	if err := json.Unmarshal(raw, &delays); err != nil {
		t.Fatal(err)
	}
	if len(delays) == 0 {
		t.Fatal("FIGANI delay metadata is empty")
	}
	for key, want := range delays {
		resource, err := strconv.Atoi(key)
		if err != nil {
			t.Fatalf("invalid FIGANI delay key %q: %v", key, err)
		}
		animation, err := figani.DecodeResource(archivePath, resource)
		if err != nil {
			t.Fatalf("FIGANI %d: %v", resource, err)
		}
		if len(want) != len(animation.Frames) {
			t.Fatalf("FIGANI %d delay frames=%d, native=%d", resource, len(want), len(animation.Frames))
		}
		for i, frame := range animation.Frames {
			if want[i] != frame.Delay {
				t.Fatalf("FIGANI %d frame %d delay=%d, native=%d", resource, i, want[i], frame.Delay)
			}
		}
	}
}
