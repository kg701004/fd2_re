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
		{"1080p", 1920, 1080, indexedmap.NativeMapViewport{Cols: 39, Rows: 22}},
		{"2560x1600 (this session's monitor)", 2560, 1600, indexedmap.NativeMapViewport{Cols: 53, Rows: 33}},
		{"4K", 3840, 2160, indexedmap.NativeMapViewport{Cols: 79, Rows: 44}},
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

// TestPickNativeMapViewportIsTightestFit proves pickNativeMapViewport finds
// the actual largest viewport the window allows -- not just *a* viewport
// that fits, but one where going one tile wider or taller in either
// dimension would no longer fit. A picker that under-uses the screen (e.g.
// snapping down to a coarse fixed step) would leave avoidable black margin,
// which is the whole point of this feature: show as much of the map as the
// screen genuinely has room for.
func TestPickNativeMapViewportIsTightestFit(t *testing.T) {
	for _, sz := range [][2]int{{640, 400}, {1024, 768}, {1920, 1080}, {2560, 1600}, {3840, 2160}} {
		got := pickNativeMapViewport(sz[0], sz[1])
		w, h := got.CanvasSize()
		if w*2 > sz[0] || h*2 > sz[1] {
			t.Fatalf("pickNativeMapViewport(%v)=%+v doesn't fit: canvas doubled %dx%d", sz, got, w*2, h*2)
		}
		wider := indexedmap.NativeMapViewport{Cols: got.Cols + 1, Rows: got.Rows}
		if ww, _ := wider.CanvasSize(); ww*2 <= sz[0] {
			t.Fatalf("pickNativeMapViewport(%v)=%+v leaves room for a wider Cols", sz, got)
		}
		taller := indexedmap.NativeMapViewport{Cols: got.Cols, Rows: got.Rows + 1}
		if _, th := taller.CanvasSize(); th*2 <= sz[1] {
			t.Fatalf("pickNativeMapViewport(%v)=%+v leaves room for a taller Rows", sz, got)
		}
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

// TestNativeMapViewportLadderStaysBoundedAndEndsAtDefault proves the ladder
// (see nativeMapViewportLadder) never exceeds preferred or the field in
// either axis, never repeats an entry, always terminates (it's a search over
// a diagonal step-down plus two axis-flattened variants per step, not a
// combinatorial blow-up), and always ends at the original 13x8 -- the
// structural properties the fallback search relies on, independent of the
// exact step values or how many axis variants it tries (both free to be
// retuned).
func TestNativeMapViewportLadderStaysBoundedAndEndsAtDefault(t *testing.T) {
	preferred := indexedmap.NativeMapViewport{Cols: 53, Rows: 33}
	ladder := nativeMapViewportLadder(preferred, 24, 24)
	if len(ladder) < 2 {
		t.Fatalf("ladder=%+v too short to show a step-down at all", ladder)
	}
	if len(ladder) > 64 {
		t.Fatalf("ladder=%+v has %d entries, expected a small bounded search", ladder, len(ladder))
	}
	if last := ladder[len(ladder)-1]; last != indexedmap.DefaultNativeMapViewport {
		t.Fatalf("ladder must end at the original 13x8, got %+v (full ladder=%+v)", last, ladder)
	}
	seen := make(map[indexedmap.NativeMapViewport]bool)
	for _, v := range ladder {
		if v.Cols > 24 || v.Rows > 24 {
			t.Fatalf("ladder entry %+v exceeds the 24x24 field (full ladder=%+v)", v, ladder)
		}
		if v.Cols > preferred.Cols || v.Rows > preferred.Rows {
			t.Fatalf("ladder entry %+v exceeds preferred %+v (full ladder=%+v)", v, preferred, ladder)
		}
		if seen[v] {
			t.Fatalf("ladder repeats entry %+v (full ladder=%+v)", v, ladder)
		}
		seen[v] = true
	}
}

// TestNativeMapViewportLadderFindsMiddleGroundNotJustDefault mirrors the
// real battle_ch01 campaign fixture (24x24 field, authored camera (1,13)):
// the widest window-fitting viewport clamps to exactly the field size,
// {24,24}, which that authored camera can't satisfy (needs CameraX<=width-
// viewCols and CameraY<=height-viewRows) -- but some narrower step in the
// ladder can. The ladder must offer that middle ground rather than forfeit
// it by jumping straight from the widest clamp to the original 13x8.
func TestNativeMapViewportLadderFindsMiddleGroundNotJustDefault(t *testing.T) {
	ladder := nativeMapViewportLadder(indexedmap.NativeMapViewport{Cols: 53, Rows: 33}, 24, 24)
	view := battle.NativeMapViewState{CameraX: 1, CameraY: 13, CursorX: 8, CursorY: 17, VisibleCursorX: 7, VisibleCursorY: 4}
	foundNonDefault := false
	for _, vp := range ladder {
		state := &battle.State{W: 24, H: 24, NativeMapViewportCols: vp.Cols, NativeMapViewportRows: vp.Rows}
		if err := state.MaterializeNativeMapViewState(view); err == nil && vp != indexedmap.DefaultNativeMapViewport {
			foundNonDefault = true
			break
		}
	}
	if !foundNonDefault {
		t.Fatalf("ladder=%+v never satisfied battle_ch01's authored camera except at the original 13x8 default", ladder)
	}
}

// TestNativeMapViewportLadderFindsWidthWhenOnlyHeightIsPinned mirrors the
// real battle_ch26 campaign fixture (31x47 field, authored camera (9,39)):
// CameraY=39 forces Rows<=47-39=8 -- exactly (never more than) the original
// height, no matter how wide the window is -- while CameraX=9 only requires
// Cols<=31-9=22, comfortably wider than the original 13. A pure diagonal
// step-down (shrinking Cols and Rows together) would reach Rows==8 only
// after Cols has also shrunk all the way to the original 13, missing the
// {22,8}-ish middle ground entirely; the axis-flattened variants in
// nativeMapViewportLadder are what actually find it.
func TestNativeMapViewportLadderFindsWidthWhenOnlyHeightIsPinned(t *testing.T) {
	ladder := nativeMapViewportLadder(indexedmap.NativeMapViewport{Cols: 53, Rows: 33}, 31, 47)
	view := battle.NativeMapViewState{CameraX: 9, CameraY: 39, CursorX: 15, CursorY: 46, VisibleCursorX: 6, VisibleCursorY: 7}
	widest := -1
	for _, vp := range ladder {
		state := &battle.State{W: 31, H: 47, NativeMapViewportCols: vp.Cols, NativeMapViewportRows: vp.Rows}
		if err := state.MaterializeNativeMapViewState(view); err == nil && vp.Cols > widest {
			widest = vp.Cols
		}
	}
	if widest <= indexedmap.DefaultNativeMapViewport.Cols {
		t.Fatalf("ladder=%+v never widened Cols past the original 13 despite Rows-only being pinned by the authored camera", ladder)
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
