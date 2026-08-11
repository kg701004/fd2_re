package main

import "github.com/wicanr2/fd2_re/remake/internal/indexedmap"

// nativeMapViewportPresets are discrete steady-map viewport sizes, widest
// first. None of these (besides the always-available original 13x8) are
// recovered EXE constants: they are a remake-only extension letting a
// window/screen bigger than the original 640x400 show more of the map
// instead of just bigger pixels (see indexedmap.NativeMapViewport). Discrete
// presets, recomputed only when the window size actually changes rather than
// continuously, keep the buffer allocation and test surface enumerable
// instead of combinatorial (see the widening plan's key design decisions).
var nativeMapViewportPresets = []indexedmap.NativeMapViewport{
	{Cols: 44, Rows: 26},
	{Cols: 35, Rows: 21},
	{Cols: 28, Rows: 17},
	{Cols: 22, Rows: 13},
	{Cols: 17, Rows: 10},
	indexedmap.DefaultNativeMapViewport, // 13x8, always available
}

// pickNativeMapViewport returns the widest preset whose doubled-pixel canvas
// (matching the existing chunky 2x-scaled look, see drawNativeMapFrame)
// still fits inside outsideW x outsideH. It always terminates at
// DefaultNativeMapViewport, which reproduces the original fixed 640x400
// presentation and therefore always fits any window the game can open.
func pickNativeMapViewport(outsideW, outsideH int) indexedmap.NativeMapViewport {
	for _, v := range nativeMapViewportPresets {
		w, h := v.CanvasSize()
		if w*2 <= outsideW && h*2 <= outsideH {
			return v
		}
	}
	return indexedmap.DefaultNativeMapViewport
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
