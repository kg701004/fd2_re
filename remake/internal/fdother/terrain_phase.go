package fdother

import "fmt"

// NativeTerrainPhaseState owns 0x11eee's steady terrain globals
// [0x53c1f]/[0x539f4]. Timer values are sign-extended low BIOS words.
type NativeTerrainPhaseState struct {
	Phase         int
	LastTimerTick int
}

// AdvanceNativeTerrainPhase reproduces 0x11eee's selector update. Override is
// raw [0x51a93]: -1 enables the BIOS-timed 20-phase cycle; 0..19 selects one
// phase directly without changing LastTimerTick. Other values fail closed
// before mutating the caller's state.
func AdvanceNativeTerrainPhase(state NativeTerrainPhaseState, rawTimerTick, override int) (NativeTerrainPhaseState, error) {
	if state.Phase < 0 || state.Phase >= 20 ||
		state.LastTimerTick < -0x8000 || state.LastTimerTick > 0x7fff ||
		rawTimerTick < -0x8000 || rawTimerTick > 0x7fff {
		return state, fmt.Errorf("fdother: native terrain phase state is outside raw bounds")
	}
	if override != -1 {
		if override < 0 || override >= 20 {
			return state, fmt.Errorf("fdother: native terrain phase override is outside table")
		}
		state.Phase = override
		return state, nil
	}
	delta := rawTimerTick - state.LastTimerTick
	if delta > 2 || rawTimerTick < state.LastTimerTick {
		state.Phase++
		if state.Phase == 20 {
			state.Phase = 0
		}
		state.LastTimerTick = rawTimerTick
	}
	return state, nil
}
