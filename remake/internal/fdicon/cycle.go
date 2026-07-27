package fdicon

// NativeMapSpriteCycleState owns the three battle-session globals consumed by
// 0x127e0 and mutated by 0x1297d.
type NativeMapSpriteCycleState struct {
	Idle, Moving  int
	LastTimerTick int
}

// AdvanceNativeMapSpriteCycles reproduces all mutations in sub_1297d.
// rawTimerTick is the sign-extended low word of BIOS timer [0x46c]. Idle
// advances only when tick-last is negative or greater than four; Moving
// advances on every compositor call. Both wrap 3→0.
func AdvanceNativeMapSpriteCycles(state NativeMapSpriteCycleState, rawTimerTick int) NativeMapSpriteCycleState {
	delta := rawTimerTick - state.LastTimerTick
	if delta > 4 || delta < 0 {
		state.Idle = (state.Idle + 1) & 3
		state.LastTimerTick = rawTimerTick
	}
	state.Moving = (state.Moving + 1) & 3
	return state
}
