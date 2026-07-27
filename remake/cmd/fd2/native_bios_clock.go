package main

import "time"

// The PC/AT BIOS timer advances at PIT channel 0 frequency / 65536:
// 1,193,182 / 65,536 ~= 18.2065 Hz. The rounded nanosecond period keeps the
// adapter integer-only; time.Time.Sub retains Go's monotonic component.
const nativeBIOSTickPeriod = 54_925_493 * time.Nanosecond

// nativeBIOSClock materializes only the signed low word read by FD2 at
// absolute 0x46c. The native animation code does not persist the daily BIOS
// counter, so a battle-local zero origin preserves all proven delta/wrap
// behavior without fabricating the host's time-of-day tick.
type nativeBIOSClock struct {
	last         time.Time
	remainder    time.Duration
	elapsedTicks uint64
}

func (c *nativeBIOSClock) Reset() {
	*c = nativeBIOSClock{}
}

func (c *nativeBIOSClock) Sample(now time.Time) int {
	if c.last.IsZero() {
		c.last = now
		return int(int16(uint16(c.elapsedTicks)))
	}
	elapsed := now.Sub(c.last)
	if elapsed < 0 {
		return int(int16(uint16(c.elapsedTicks)))
	}
	c.last = now
	c.remainder += elapsed
	if ticks := c.remainder / nativeBIOSTickPeriod; ticks > 0 {
		c.elapsedTicks += uint64(ticks)
		c.remainder -= ticks * nativeBIOSTickPeriod
	}
	return int(int16(uint16(c.elapsedTicks)))
}

// advanceNativeMapClock reproduces the one 0x1297d call at the head of each
// 0x11cac redraw, followed by the independent terrain/unit BIOS-word latches
// consumed by that same frame. A legacy or partially materialized State is
// left untouched.
func (g *Game) advanceNativeMapClock(now time.Time) bool {
	if g == nil || g.st == nil ||
		!g.st.HasNativeMapCycleState ||
		!g.st.HasNativeTerrainPhaseState ||
		!g.st.HasNativeMapBinaryTimingState ||
		!g.st.HasNativeMapViewState {
		return false
	}
	rawTick := g.nativeMapClock.Sample(now)
	return g.st.AdvanceNativeMapPresentationCycles(rawTick) &&
		g.st.AdvanceNativeTerrainPhase(rawTick, -1) &&
		g.st.AdvanceNativeTerrainFlip(rawTick) &&
		g.st.AdvanceNativeUnitPixelShift(rawTick)
}
