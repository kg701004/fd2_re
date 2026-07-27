package fdicon

import "fmt"

// NativeBinaryTickState owns one native 0/1 animation global and its
// sign-extended low-BIOS-word latch. 0x11eee uses one instance for terrain;
// 0x127e0 uses an independent instance for unit pixel shift.
type NativeBinaryTickState struct {
	Value         int
	LastTimerTick int
}

// AdvanceNativeBinaryTick reproduces the shared "new BIOS word toggles bit"
// sequence. The two native call sites own separate instances and call timing.
func AdvanceNativeBinaryTick(state NativeBinaryTickState, rawTimerTick int) (NativeBinaryTickState, error) {
	if (state.Value != 0 && state.Value != 1) ||
		state.LastTimerTick < -0x8000 || state.LastTimerTick > 0x7fff ||
		rawTimerTick < -0x8000 || rawTimerTick > 0x7fff {
		return state, fmt.Errorf("fdicon: native binary tick state is outside raw bounds")
	}
	if rawTimerTick != state.LastTimerTick {
		state.Value ^= 1
		state.LastTimerTick = rawTimerTick
	}
	return state, nil
}
