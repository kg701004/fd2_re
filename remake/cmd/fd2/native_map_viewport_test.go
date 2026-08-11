package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/indexedmap"
)

func TestPickNativeMapViewportFitsRealWindowSizes(t *testing.T) {
	for _, tc := range []struct {
		name     string
		outsideW int
		outsideH int
		want     indexedmap.NativeMapViewport
	}{
		{"exact original window", 640, 400, indexedmap.DefaultNativeMapViewport},
		{"smaller than original", 320, 200, indexedmap.DefaultNativeMapViewport},
		{"1080p", 1920, 1080, indexedmap.NativeMapViewport{Cols: 35, Rows: 21}},
		{"2560x1600 (this session's monitor)", 2560, 1600, indexedmap.NativeMapViewport{Cols: 44, Rows: 26}},
		{"4K", 3840, 2160, indexedmap.NativeMapViewport{Cols: 44, Rows: 26}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got := pickNativeMapViewport(tc.outsideW, tc.outsideH)
			if got != tc.want {
				t.Fatalf("pickNativeMapViewport(%d,%d) = %+v, want %+v", tc.outsideW, tc.outsideH, got, tc.want)
			}
			// The default is a floor, not just another preset: a window
			// smaller than the original 640x400 still gets it (the app
			// doesn't support going below that), so the doubled-canvas-fits
			// check below only holds once the window is at least that size.
			if tc.outsideW < 640 || tc.outsideH < 400 {
				return
			}
			w, h := got.CanvasSize()
			if w*2 > tc.outsideW || h*2 > tc.outsideH {
				t.Fatalf("picked viewport %+v doubled canvas %dx%d exceeds window %dx%d", got, w*2, h*2, tc.outsideW, tc.outsideH)
			}
		})
	}
}

func TestPickNativeMapViewportPresetsAreMonotonicAndAlwaysFitDefault(t *testing.T) {
	prevArea := 0
	for i := len(nativeMapViewportPresets) - 1; i >= 0; i-- {
		v := nativeMapViewportPresets[i]
		area := v.Cols * v.Rows
		if area < prevArea {
			t.Fatalf("preset %+v is smaller than a narrower-window preset before it", v)
		}
		prevArea = area
	}
	if nativeMapViewportPresets[len(nativeMapViewportPresets)-1] != indexedmap.DefaultNativeMapViewport {
		t.Fatal("narrowest preset must be DefaultNativeMapViewport so every window size has a fallback")
	}
}

func TestClampNativeMapViewportToFieldNeverExceedsFieldOrShrinksBelowDefault(t *testing.T) {
	wide := indexedmap.NativeMapViewport{Cols: 44, Rows: 26}
	if got := clampNativeMapViewportToField(wide, 20, 15); got != (indexedmap.NativeMapViewport{Cols: 20, Rows: 15}) {
		t.Fatalf("field-clamped viewport = %+v, want {20,15}", got)
	}
	if got := clampNativeMapViewportToField(wide, 100, 100); got != wide {
		t.Fatalf("viewport clamped against a larger field changed: got %+v, want unchanged %+v", got, wide)
	}
	if got := clampNativeMapViewportToField(indexedmap.DefaultNativeMapViewport, 13, 8); got != indexedmap.DefaultNativeMapViewport {
		t.Fatalf("default viewport against exact-size field = %+v, want unchanged default", got)
	}
}

// TestNativeMapViewportLadderFallsBackToNarrowerPresetNotStraightToDefault
// mirrors the real battle_ch01 campaign fixture (24x24 field, authored
// camera (1,13)): the widest window-fitting preset {44,26} clamps to
// {24,24}, which the authored camera can't satisfy (needs CameraX<=width-
// viewCols and CameraY<=height-viewRows), but the narrower {17,10} preset
// can. The ladder must offer that middle ground, not jump straight from the
// widest preset to the original 13x8 default.
func TestNativeMapViewportLadderFallsBackToNarrowerPresetNotStraightToDefault(t *testing.T) {
	ladder := nativeMapViewportLadder(indexedmap.NativeMapViewport{Cols: 44, Rows: 26}, 24, 24)
	want := []indexedmap.NativeMapViewport{
		{Cols: 24, Rows: 24}, {Cols: 24, Rows: 21}, {Cols: 24, Rows: 17},
		{Cols: 22, Rows: 13}, {Cols: 17, Rows: 10}, {Cols: 13, Rows: 8},
	}
	if len(ladder) != len(want) {
		t.Fatalf("ladder=%+v, want %+v", ladder, want)
	}
	for i := range want {
		if ladder[i] != want[i] {
			t.Fatalf("ladder[%d]=%+v, want %+v (full ladder=%+v)", i, ladder[i], want[i], ladder)
		}
	}
	found := false
	for _, vp := range ladder {
		if vp == (indexedmap.NativeMapViewport{Cols: 17, Rows: 10}) {
			found = true
			view := battle.NativeMapViewState{CameraX: 1, CameraY: 13, CursorX: 8, CursorY: 17, VisibleCursorX: 7, VisibleCursorY: 4}
			state := &battle.State{W: 24, H: 24, NativeMapViewportCols: vp.Cols, NativeMapViewportRows: vp.Rows}
			if err := state.MaterializeNativeMapViewState(view); err != nil {
				t.Fatalf("battle_ch01's authored camera rejected {17,10}: %v", err)
			}
		}
	}
	if !found {
		t.Fatal("ladder never offered {17,10}, the preset battle_ch01's authored camera actually fits")
	}
}

// TestLayoutPicksAndCachesNativeMapViewport proves Layout actually recomputes
// g.nativeMapViewport from the returned window size, and only when that size
// changes -- not, say, leaving it at the zero value or recomputing every call
// regardless of size (which would defeat the point of caching it at all).
func TestLayoutPicksAndCachesNativeMapViewport(t *testing.T) {
	g := &Game{}
	if w, h := g.Layout(2560, 1600); w != 2560 || h != 1600 {
		t.Fatalf("Layout(2560,1600) = (%d,%d)", w, h)
	}
	want := pickNativeMapViewport(2560, 1600)
	if g.nativeMapViewport != want {
		t.Fatalf("nativeMapViewport=%+v after Layout(2560,1600), want %+v", g.nativeMapViewport, want)
	}
	if g.nativeMapViewportForW != 2560 || g.nativeMapViewportForH != 1600 {
		t.Fatalf("cached size=(%d,%d), want (2560,1600)", g.nativeMapViewportForW, g.nativeMapViewportForH)
	}
	// Poison the cached viewport directly and call Layout again with the same
	// size: the cache-compare must skip recomputation and leave it poisoned,
	// proving the cache actually gates the recompute rather than being
	// decorative.
	g.nativeMapViewport = indexedmap.NativeMapViewport{Cols: 999, Rows: 999}
	if w, h := g.Layout(2560, 1600); w != 2560 || h != 1600 {
		t.Fatalf("Layout(2560,1600) second call = (%d,%d)", w, h)
	}
	if g.nativeMapViewport != (indexedmap.NativeMapViewport{Cols: 999, Rows: 999}) {
		t.Fatalf("same-size Layout call recomputed nativeMapViewport: got %+v", g.nativeMapViewport)
	}
	// A genuine size change must recompute it.
	if w, h := g.Layout(640, 400); w != 640 || h != 400 {
		t.Fatalf("Layout(640,400) = (%d,%d)", w, h)
	}
	if g.nativeMapViewport != indexedmap.DefaultNativeMapViewport {
		t.Fatalf("nativeMapViewport after a real size change=%+v, want DefaultNativeMapViewport", g.nativeMapViewport)
	}
}
