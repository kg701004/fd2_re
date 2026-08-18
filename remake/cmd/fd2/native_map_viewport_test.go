package main

import (
	"image"
	"image/png"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/hajimehoshi/ebiten/v2"
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

// TestHasHDNativeTerrainReflectsLoadedTileCellScale proves hasHDNativeTerrain
// tracks g.tileCellScale (loadMap's own detection, see
// TestTileCellScaleForDetectsUpscaledTilesets) rather than re-deriving
// anything itself, so the two can never disagree.
func TestHasHDNativeTerrainReflectsLoadedTileCellScale(t *testing.T) {
	g := &Game{m: &MapData{Cols: 16, TileW: 24, TileH: 24}}
	if g.hasHDNativeTerrain() {
		t.Fatal("nil tileset must report no HD terrain")
	}
	g.tileset = ebiten.NewImage(16*24, 18*24) // native-resolution sheet
	g.tileCellScale = 1
	if g.hasHDNativeTerrain() {
		t.Fatal("tileCellScale=1 reported as HD")
	}
	g.tileset = ebiten.NewImage(16*24*4, 18*24*4) // 4x-upscaled sheet
	g.tileCellScale = 4
	if !g.hasHDNativeTerrain() {
		t.Fatal("tileCellScale=4 not detected as HD")
	}
}

// TestTileCellScaleForDetectsUpscaledTilesets proves the exact formula
// loadMap uses to detect an upscaled tileset.png without needing real
// map.json/tileset.png fixtures on disk.
func TestTileCellScaleForDetectsUpscaledTilesets(t *testing.T) {
	cases := []struct {
		name                string
		tsW, cols, tileW    int
		want                int
	}{
		{"native 16 cols * 24px", 384, 16, 24, 1},
		{"4x upscale of the same sheet", 1536, 16, 24, 4},
		{"2x upscale", 768, 16, 24, 2},
		{"narrower than one native row is not an upscale", 100, 16, 24, 1},
		{"cols=0 guards against divide by zero", 384, 0, 24, 1},
		{"tileW=0 guards against divide by zero", 384, 16, 0, 1},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := tileCellScaleFor(c.tsW, c.cols, c.tileW); got != c.want {
				t.Fatalf("tileCellScaleFor(%d,%d,%d)=%d, want %d", c.tsW, c.cols, c.tileW, got, c.want)
			}
		})
	}
}

func writeTestPNG(t *testing.T, path string, w, h int) {
	t.Helper()
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := png.Encode(f, image.NewRGBA(image.Rect(0, 0, w, h))); err != nil {
		t.Fatal(err)
	}
}

// awaitMapCompositeAsync blocks (with a generous test timeout) for
// startLoadMapCompositeAsync's background goroutine to finish, since tests
// need a synchronous result even though production code (Update()'s
// pollMapCompositeAsync) deliberately never blocks on it.
func awaitMapCompositeAsync(t *testing.T, ch <-chan mapCompositeAsyncResult) mapCompositeAsyncResult {
	t.Helper()
	select {
	case res := <-ch:
		return res
	case <-time.After(5 * time.Second):
		t.Fatal("startLoadMapCompositeAsync did not complete in time")
		return mapCompositeAsyncResult{}
	}
}

// TestLoadMapCompositeUsesWholeMapImageWhenPresent proves loadMap's
// whole-map-composite detection (the seam fix: one upscaled image per map
// instead of a per-tile grid, see startLoadMapCompositeAsync/
// apply_hd_composite.py) measures its scale the same self-describing way
// tileCellScaleFor does for per-tile sheets, rather than assuming a
// hardcoded 4x.
func TestLoadMapCompositeUsesWholeMapImageWhenPresent(t *testing.T) {
	dir := t.TempDir()
	m := &MapData{W: 3, H: 2, TileW: 24, TileH: 24}
	writeTestPNG(t, filepath.Join(dir, "map_composite.png"), 3*24*4, 2*24*4)

	res := awaitMapCompositeAsync(t, startLoadMapCompositeAsync(dir, m))
	if res.img == nil {
		t.Fatal("expected composite image to load")
	}
	if res.scale != 4 {
		t.Fatalf("scale=%d, want 4", res.scale)
	}
}

// TestLoadMapCompositeAbsentFallsBackToTileGrid proves a map with no
// map_composite.png (most maps, until each is individually run through the
// compose+upscale pipeline) is not an error -- Draw() must keep using the
// existing tile-grid renderer unchanged.
func TestLoadMapCompositeAbsentFallsBackToTileGrid(t *testing.T) {
	dir := t.TempDir()
	m := &MapData{W: 3, H: 2, TileW: 24, TileH: 24}
	res := awaitMapCompositeAsync(t, startLoadMapCompositeAsync(dir, m))
	if res.img != nil || res.scale != 0 {
		t.Fatalf("expected nil/0 for missing composite, got %v/%d", res.img, res.scale)
	}
}

// TestLoadMapCompositeRejectsMismatchedDimensions proves a corrupt/wrong-size
// composite file falls back to the tile grid rather than being drawn
// distorted or cropped.
func TestLoadMapCompositeRejectsMismatchedDimensions(t *testing.T) {
	dir := t.TempDir()
	m := &MapData{W: 3, H: 2, TileW: 24, TileH: 24}
	writeTestPNG(t, filepath.Join(dir, "map_composite.png"), 3*24*4, 2*24*4+7)

	res := awaitMapCompositeAsync(t, startLoadMapCompositeAsync(dir, m))
	if res.img != nil || res.scale != 0 {
		t.Fatalf("expected fallback for mismatched composite, got %v/%d", res.img, res.scale)
	}
}

// TestPollMapCompositeAsyncAppliesResultOnMainGoroutine proves
// pollMapCompositeAsync (Update()'s per-frame hook) both does nothing when
// no decode is in flight/not yet finished, and applies + clears the pending
// channel once a result is available -- the mechanism that lets Draw() see
// the HD composite a few frames after loadMap() returns, instead of
// blocking loadMap() itself on the slow decode.
func TestPollMapCompositeAsyncAppliesResultOnMainGoroutine(t *testing.T) {
	g := &Game{}
	g.pollMapCompositeAsync() // no pending channel: must be a no-op, not a panic

	dir := t.TempDir()
	m := &MapData{W: 3, H: 2, TileW: 24, TileH: 24}
	writeTestPNG(t, filepath.Join(dir, "map_composite.png"), 3*24*4, 2*24*4)
	ch := startLoadMapCompositeAsync(dir, m)
	awaitMapCompositeAsync(t, ch) // drain it directly so the retest below can push straight to poll

	// Re-run for real against g via a fresh channel so pollMapCompositeAsync
	// exercises the actual field, not just the free function.
	g.mapCompositePending = startLoadMapCompositeAsync(dir, m)
	deadline := time.Now().Add(5 * time.Second)
	for g.mapComposite == nil && time.Now().Before(deadline) {
		g.pollMapCompositeAsync()
	}
	if g.mapComposite == nil {
		t.Fatal("pollMapCompositeAsync never applied the finished decode")
	}
	if g.mapCompositePending != nil {
		t.Fatal("pollMapCompositeAsync left mapCompositePending set after applying a result")
	}
	if g.mapCompositeScale != 4 {
		t.Fatalf("mapCompositeScale=%d, want 4", g.mapCompositeScale)
	}
}

// TestHasHDNativeTerrainReflectsLoadedMapComposite proves hasHDNativeTerrain
// also recognizes the whole-map-composite HD source, not just the per-tile
// tileCellScale one (see TestHasHDNativeTerrainReflectsLoadedTileCellScale).
func TestHasHDNativeTerrainReflectsLoadedMapComposite(t *testing.T) {
	g := &Game{m: &MapData{Cols: 16, TileW: 24, TileH: 24}}
	if g.hasHDNativeTerrain() {
		t.Fatal("nil tileset/composite must report no HD terrain")
	}
	g.mapComposite = ebiten.NewImage(16*24*4, 18*24*4)
	if !g.hasHDNativeTerrain() {
		t.Fatal("loaded mapComposite not detected as HD")
	}
}
