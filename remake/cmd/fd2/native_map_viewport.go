package main

import "github.com/wicanr2/fd2_re/remake/internal/indexedmap"

// pickNativeMapViewport returns the largest viewport (in whole tiles) whose
// doubled-pixel canvas (matching the existing chunky 2x-scaled look, see
// drawNativeMapFrame) still fits inside outsideW x outsideH -- i.e. the
// tightest fit the screen actually allows, not a hand-picked step below it.
// None of this (besides the always-available original 13x8 floor) is a
// recovered EXE constant: it's a remake-only extension letting a
// window/screen bigger than the original 640x400 show as much more of the
// map as the screen genuinely has room for, instead of leaving avoidable
// unused space. Cols and Rows are found independently since canvas width
// only depends on Cols and canvas height only depends on Rows.
func pickNativeMapViewport(outsideW, outsideH int) indexedmap.NativeMapViewport {
	best := indexedmap.DefaultNativeMapViewport
	for {
		v := indexedmap.NativeMapViewport{Cols: best.Cols + 1, Rows: best.Rows}
		w, _ := v.CanvasSize()
		if w*2 > outsideW {
			break
		}
		best.Cols++
	}
	for {
		v := indexedmap.NativeMapViewport{Cols: best.Cols, Rows: best.Rows + 1}
		_, h := v.CanvasSize()
		if h*2 > outsideH {
			break
		}
		best.Rows++
	}
	return best
}

// effectiveNativeMapViewport is the viewport actually in force for the
// current battle: once materializeNativeMapRuntime locks one in on
// g.st.NativeMapViewportCols/Rows (falling back to the original size when a
// wider preset didn't fit that battle's authored camera position, see
// clampNativeMapViewportToField's caller), every frame composition, camera
// scroll and HUD anchor dodge for that battle must agree on the same size --
// this is the single shared source of truth for all of them, deliberately
// not re-picked from g.nativeMapViewport every frame (see the Phase 5 note
// in composeNativeMapFrameAt).
func (g *Game) effectiveNativeMapViewport() indexedmap.NativeMapViewport {
	if g.st == nil || g.st.NativeMapViewportCols <= 0 || g.st.NativeMapViewportRows <= 0 {
		return indexedmap.DefaultNativeMapViewport
	}
	return indexedmap.NativeMapViewport{Cols: g.st.NativeMapViewportCols, Rows: g.st.NativeMapViewportRows}
}

// nativeMapViewportLadder returns candidate viewports to try for a battle,
// widest first: preferred (see pickNativeMapViewport), then a geometric
// step-down (~20% smaller each step, matching how far apart this feature's
// original hand-picked presets used to be) until reaching the original 13x8.
// At every step it also tries two axis-flattened variants -- this step's
// Cols with the original Rows, and the original Cols with this step's Rows
// -- clamped to the field's own size (see clampNativeMapViewportToField) and
// deduped.
//
// The axis-flattened variants matter: a campaign-authored camera position
// (see materializeNativeMapRuntime) can pin one axis hard against the
// field's edge while leaving the other one free -- e.g. battle_ch26's
// authored camera only ever satisfies Rows==8 (the original height, no
// matter how wide the window is) while Cols could legitimately go up to 22.
// A pure diagonal shrink never visits {22,8} since both axes shrink
// together, so it would silently forfeit that width. Trying the flattened
// variants at each step finds it. This is still a small, bounded search (not
// combinatorial): at most 3 candidates per geometric step, a handful of
// steps.
//
// The original 13x8 default is always last, since every field must be at
// least that size for the game to be playable at all today.
func nativeMapViewportLadder(preferred indexedmap.NativeMapViewport, fieldW, fieldH int) []indexedmap.NativeMapViewport {
	def := indexedmap.DefaultNativeMapViewport
	seen := make(map[indexedmap.NativeMapViewport]bool)
	ladder := make([]indexedmap.NativeMapViewport, 0, 16)
	add := func(v indexedmap.NativeMapViewport) {
		clamped := clampNativeMapViewportToField(v, fieldW, fieldH)
		if clamped == def || seen[clamped] {
			return // def is appended once, unconditionally, after the loop
		}
		seen[clamped] = true
		ladder = append(ladder, clamped)
	}
	for cur := preferred; cur != def; {
		add(cur)
		add(indexedmap.NativeMapViewport{Cols: cur.Cols, Rows: def.Rows})
		add(indexedmap.NativeMapViewport{Cols: def.Cols, Rows: cur.Rows})
		next := indexedmap.NativeMapViewport{
			Cols: cur.Cols - cur.Cols/5,
			Rows: cur.Rows - cur.Rows/5,
		}
		if next.Cols <= def.Cols {
			next.Cols = def.Cols
		}
		if next.Rows <= def.Rows {
			next.Rows = def.Rows
		}
		if next == cur { // geometric step rounded to nothing: force one tile
			if next.Cols > def.Cols {
				next.Cols--
			}
			if next.Rows > def.Rows {
				next.Rows--
			}
		}
		cur = next
	}
	ladder = append(ladder, clampNativeMapViewportToField(def, fieldW, fieldH))
	return ladder
}

// clampNativeMapViewportToField shrinks a candidate viewport so it never
// exceeds the current battle's own field dimensions -- a viewport wider or
// taller than the field itself has no valid camera position at all (see
// battle.validateNativeMapView's CameraX <= width-viewCols bound). v is
// always pickNativeMapViewport's result, which is never smaller than
// DefaultNativeMapViewport (13x8); every original field is at least that
// size too (the fixed original viewport already required it), so this only
// ever shrinks toward, never below, the original default.
func clampNativeMapViewportToField(v indexedmap.NativeMapViewport, fieldW, fieldH int) indexedmap.NativeMapViewport {
	if fieldW > 0 && v.Cols > fieldW {
		v.Cols = fieldW
	}
	if fieldH > 0 && v.Rows > fieldH {
		v.Rows = fieldH
	}
	return v
}
