package main

const (
	actionOverlayOpening = "opening"
	actionOverlayOpen    = "open"
	actionOverlayClosing = "closing"
)

// beginActionOverlayOpen starts the four presents recovered at 0x1741c.
// There is no delay call between native presents, so the remake assigns one
// presented Ebiten frame to each step without claiming an original duration.
func (g *Game) beginActionOverlayOpen(selection int) {
	g.ring = true
	g.ringSel = selection
	g.actionOverlayPhase = actionOverlayOpening
	g.actionOverlayFrame = 0
	g.actionOverlayAfter = nil
	g.actionOverlayDrawn = false
	g.actionOverlayShotHold = false
	g.resetRingPulse()
}

// resetRingPulse restarts the selected-cell blink cadence whenever the ring
// (re)opens; it keeps ticking across arrow-key selection changes within the
// same open session, same as the sibling native menus. 2026-08-13: added because the ring's
// selection border was a flat static color while every sibling native menu
// in this codebase (town/church/shop/class -- see nativeTownUIPulse and its
// siblings) blinks its selected cell on a 4-tick BIOS-clock cadence, ported
// from actual disassembly of those menus' own routines (e.g. 0x2d1b5 for
// town). No equivalent disassembly offset for THIS menu's own selected-cell
// blink is on file yet (doc51 only confirms doc13's state-machine offsets
// 0x18ED0/0x18890 for the menu structure itself, not its blink timing), so
// this reuses the same proven cadence/mechanism for visual consistency
// rather than claiming a byte-verified port -- flagged in
// docs/knowledge-base for follow-up RE work if the exact original timing
// ever gets confirmed.
func (g *Game) resetRingPulse() {
	g.ringUIClock.Reset()
	g.ringPulse = 0
	g.ringLastTick = 0
	g.ringHasTick = false
}

// stepRingPulseTick mirrors stepNativeTownUIPulseTick's proven 4-tick-delta,
// four-state wrap-around cadence.
func (g *Game) stepRingPulseTick(rawTick int) {
	if !g.ringHasTick {
		g.ringLastTick = rawTick
		g.ringHasTick = true
		return
	}
	delta := int16(uint16(rawTick) - uint16(g.ringLastTick))
	if delta < 4 {
		return
	}
	g.ringLastTick = rawTick
	g.ringPulse = (g.ringPulse + 1) & 3
}

// beginActionOverlayClose starts the independent four-present sequence from
// 0x176b4. The selected action is deferred until all four close frames have
// been presented; it must not appear beneath an overlay that native code was
// still closing.
func (g *Game) beginActionOverlayClose(after func()) {
	if !g.ring {
		if after != nil {
			after()
		}
		return
	}
	g.actionOverlayPhase = actionOverlayClosing
	g.actionOverlayFrame = 0
	g.actionOverlayAfter = after
	g.actionOverlayDrawn = false
	g.actionOverlayShotHold = false
}

func (g *Game) actionOverlayBlocksInput() bool {
	return g.actionOverlayPhase == actionOverlayOpening ||
		g.actionOverlayPhase == actionOverlayClosing
}

func (g *Game) actionOverlayRenderState() (frame int, closing bool) {
	switch g.actionOverlayPhase {
	case actionOverlayOpening:
		return g.actionOverlayFrame, false
	case actionOverlayClosing:
		return g.actionOverlayFrame, true
	default:
		return 3, false
	}
}

// stepActionOverlayLifecycle runs once near the start of Update. A sequence is
// initialized later in an input Update, so frame zero is drawn before the next
// call advances it. The callback similarly runs only after close frame three
// was available to Draw for a complete update interval.
func (g *Game) stepActionOverlayLifecycle() {
	if g.actionOverlayShotHold {
		return
	}
	if g.actionOverlayBlocksInput() && !g.actionOverlayDrawn {
		return
	}
	switch g.actionOverlayPhase {
	case actionOverlayOpening:
		if g.actionOverlayFrame < 3 {
			g.actionOverlayFrame++
			g.actionOverlayDrawn = false
			return
		}
		g.actionOverlayPhase = actionOverlayOpen
		g.actionOverlayDrawn = false
	case actionOverlayClosing:
		if g.actionOverlayFrame < 3 {
			g.actionOverlayFrame++
			g.actionOverlayDrawn = false
			return
		}
		after := g.actionOverlayAfter
		g.actionOverlayPhase = ""
		g.actionOverlayFrame = 0
		g.actionOverlayAfter = nil
		g.actionOverlayDrawn = false
		g.ring = false
		if after != nil {
			after()
		}
	}
}

func (g *Game) markActionOverlayDrawn() {
	if g.actionOverlayBlocksInput() {
		g.actionOverlayDrawn = true
	}
}

func (g *Game) resetActionOverlayLifecycle() {
	g.ring = false
	g.actionOverlayPhase = ""
	g.actionOverlayFrame = 0
	g.actionOverlayAfter = nil
	g.actionOverlayDrawn = false
	g.actionOverlayShotHold = false
}
