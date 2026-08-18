package main

import "testing"

// TestRingPulseUsesFourTickSignedDelta mirrors
// TestNativeTownPulseUsesFourTickSignedDelta's exact tick sequence and signed
// 16-bit wraparound boundary (0x7fff -> -0x8000) -- ringPulse reuses the same
// cadence/mechanism as nativeTownUIPulse (see resetRingPulse's doc comment).
func TestRingPulseUsesFourTickSignedDelta(t *testing.T) {
	g := &Game{}
	for _, tc := range []struct {
		tick int
		want int
	}{
		{0x7ffe, 0},
		{0x7fff, 0},
		{-0x7ffe, 1},
		{-0x7ffa, 2},
		{-0x7ff6, 3},
		{-0x7ff2, 0},
	} {
		g.stepRingPulseTick(tc.tick)
		if g.ringPulse != tc.want {
			t.Fatalf("tick %#x pulse=%d want %d", tc.tick, g.ringPulse, tc.want)
		}
	}
}

// TestRingPulseSubFourTickDeltaDoesNotAdvance confirms a delta below the
// 4-tick threshold leaves the counter untouched (only the internal last-tick
// baseline updates on the very first sample).
func TestRingPulseSubFourTickDeltaDoesNotAdvance(t *testing.T) {
	g := &Game{}
	g.stepRingPulseTick(100) // first sample: only seeds ringLastTick
	if g.ringPulse != 0 {
		t.Fatalf("first sample pulse=%d want 0", g.ringPulse)
	}
	g.stepRingPulseTick(103) // delta=3 < 4: must not advance
	if g.ringPulse != 0 || g.ringLastTick != 100 {
		t.Fatalf("sub-threshold delta advanced state: pulse=%d lastTick=%d", g.ringPulse, g.ringLastTick)
	}
	g.stepRingPulseTick(104) // delta=4 from the still-unmoved baseline: advances once
	if g.ringPulse != 1 || g.ringLastTick != 104 {
		t.Fatalf("threshold delta did not advance: pulse=%d lastTick=%d", g.ringPulse, g.ringLastTick)
	}
}

// TestBeginActionOverlayOpenResetsRingPulse confirms opening the ring restarts
// the blink cadence from a clean state, matching resetRingPulse's contract.
func TestBeginActionOverlayOpenResetsRingPulse(t *testing.T) {
	g := &Game{}
	g.stepRingPulseTick(0)
	g.stepRingPulseTick(4)
	g.stepRingPulseTick(8)
	if g.ringPulse == 0 && !g.ringHasTick {
		t.Fatal("test setup did not advance ring pulse state")
	}
	g.beginActionOverlayOpen(0)
	if g.ringPulse != 0 || g.ringHasTick || g.ringLastTick != 0 {
		t.Fatalf("beginActionOverlayOpen did not reset ring pulse: pulse=%d hasTick=%v lastTick=%d",
			g.ringPulse, g.ringHasTick, g.ringLastTick)
	}
}
