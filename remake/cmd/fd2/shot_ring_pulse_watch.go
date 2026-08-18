package main

import "os"

// stepShotRingPulseWatch opens the battle command ring as early as possible
// (mirroring stepShotShopBuyConfirm/stepShotForceResult's fix for the same
// class of bug) so the selected cell's real-wall-clock-driven blink
// (stepRingPulseTick, driven by g.ringUIClock.Sample(time.Now()) in the
// normal Update() loop) gets the intervening FD2_SHOT_FRAME-worth of real
// frames/wall-clock time to actually advance before the screenshot fires.
//
// 2026-08-16: this is deliberately separate from the existing FD2_SHOT_RING
// hook, which serves a different purpose -- freezing one specific known
// open/close animation frame for pixel-comparison oracles (FD2_SHOT_RING_FRAME)
// -- and stays inside the tight shotSetup gate (g.frame >= g.shotFrame-1) on
// purpose, since a frozen oracle frame doesn't need real elapsed time. Trying
// to reuse that path to observe the steady-state pulse instead produced
// pixel-identical screenshots: the ring only opens in the same setup pass as
// the capture, leaving ~0 real time for stepRingPulseTick's delta>=4 gate to
// ever trip.
//
// Using this hook instead surfaced a real, separate bug: g.ringPulse (state)
// was updating correctly the whole time, but drawNativeActionOverlay -- the
// renderer path any player who supplies their own original FDOTHER.DAT
// actually sees -- never read it. The 2026-08-13 pulse feature had only ever
// been wired into the classic text/color-fallback ring renderer, so the
// blink was a real no-op for the common case. Fixed alongside this hook (see
// the border-drawing block in drawNativeActionOverlay); confirmed via a
// cropped/zoomed pixel comparison showing the selected cell's border
// genuinely shifting from bright to dark orange between frame 1 and frame
// 300 of the same run. See docs/knowledge-base/58-remake-live-verification-
// log.md's ring-pulse section for the full diagnosis and evidence.
func (g *Game) stepShotRingPulseWatch() {
	if g.debugRingPulseWatchInitiated {
		return
	}
	if os.Getenv("FD2_SHOT_RING_PULSE_WATCH") == "" || g.st == nil {
		return
	}
	g.debugRingPulseWatchInitiated = true
	g.dialog = nil
	for _, unit := range g.st.Units {
		if unit != nil {
			g.sel, g.curX, g.curY = unit, unit.X, unit.Y
			break
		}
	}
	if g.sel == nil {
		return
	}
	g.moved, g.reach = true, nil
	g.beginActionOverlayOpen(1)
	g.actionOverlayPhase = actionOverlayOpen
	g.actionOverlayFrame = 3
}
