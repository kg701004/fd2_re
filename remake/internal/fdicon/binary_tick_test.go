package fdicon

import "testing"

func TestAdvanceNativeBinaryTickMatchesNativeLatch(t *testing.T) {
	state := NativeBinaryTickState{}
	var err error
	state, err = AdvanceNativeBinaryTick(state, 0)
	if err != nil || state != (NativeBinaryTickState{}) {
		t.Fatalf("same tick=%+v err=%v", state, err)
	}
	state, err = AdvanceNativeBinaryTick(state, 1)
	if err != nil || state != (NativeBinaryTickState{Value: 1, LastTimerTick: 1}) {
		t.Fatalf("first tick=%+v err=%v", state, err)
	}
	state, err = AdvanceNativeBinaryTick(state, 1)
	if err != nil || state != (NativeBinaryTickState{Value: 1, LastTimerTick: 1}) {
		t.Fatalf("repeated tick=%+v err=%v", state, err)
	}
	state, err = AdvanceNativeBinaryTick(state, -0x8000)
	if err != nil || state != (NativeBinaryTickState{LastTimerTick: -0x8000}) {
		t.Fatalf("signed wrap tick=%+v err=%v", state, err)
	}
}
