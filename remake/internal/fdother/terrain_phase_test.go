package fdother

import "testing"

func TestAdvanceNativeTerrainPhaseMatches11EEE(t *testing.T) {
	state := NativeTerrainPhaseState{}
	var err error
	state, err = AdvanceNativeTerrainPhase(state, 2, -1)
	if err != nil || state != (NativeTerrainPhaseState{}) {
		t.Fatalf("two-tick gate=%+v err=%v", state, err)
	}
	state, err = AdvanceNativeTerrainPhase(state, 3, -1)
	if err != nil || state != (NativeTerrainPhaseState{Phase: 1, LastTimerTick: 3}) {
		t.Fatalf("three-tick advance=%+v err=%v", state, err)
	}
	state, err = AdvanceNativeTerrainPhase(state, 4, -1)
	if err != nil || state != (NativeTerrainPhaseState{Phase: 1, LastTimerTick: 3}) {
		t.Fatalf("gated advance=%+v err=%v", state, err)
	}
	state = NativeTerrainPhaseState{Phase: 19, LastTimerTick: 0x7fff}
	state, err = AdvanceNativeTerrainPhase(state, -0x8000, -1)
	if err != nil || state != (NativeTerrainPhaseState{LastTimerTick: -0x8000}) {
		t.Fatalf("signed wrap advance=%+v err=%v", state, err)
	}
}

func TestAdvanceNativeTerrainPhaseOverrideDoesNotTouchTimer(t *testing.T) {
	state := NativeTerrainPhaseState{Phase: 7, LastTimerTick: 123}
	got, err := AdvanceNativeTerrainPhase(state, 456, 12)
	if err != nil || got != (NativeTerrainPhaseState{Phase: 12, LastTimerTick: 123}) {
		t.Fatalf("override=%+v err=%v", got, err)
	}
	for _, override := range []int{-2, 20} {
		if got, err := AdvanceNativeTerrainPhase(state, 456, override); err == nil || got != state {
			t.Fatalf("invalid override %d state=%+v err=%v", override, got, err)
		}
	}
}
