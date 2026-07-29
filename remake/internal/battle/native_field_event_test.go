package battle

import "testing"

func TestNativeFieldEventIDAtMatchesSelector(t *testing.T) {
	st := &State{
		W: 2, H: 2,
		NativeFieldEventSlots: []int{-1, 3, -1, -1},
		NativeFieldEvents:     make([]NativeFieldEvent, 16),
	}
	st.NativeFieldEvents[3] = NativeFieldEvent{EventID: 82, Selector: 1}
	if got, ok := NativeFieldEventIDAt(st, 1, 0, 1); !ok || got != 82 {
		t.Fatalf("event = (%d,%v), want (82,true)", got, ok)
	}
	if _, ok := NativeFieldEventIDAt(st, 1, 0, 0); ok {
		t.Fatal("selector mismatch unexpectedly accepted")
	}
}

func TestNativeFieldEventIDAtFailsClosed(t *testing.T) {
	st := &State{W: 1, H: 1, NativeFieldEventSlots: []int{0}}
	if _, ok := NativeFieldEventIDAt(st, 0, 0, 0); ok {
		t.Fatal("missing table unexpectedly accepted")
	}
	st.NativeFieldEvents = make([]NativeFieldEvent, 16)
	st.NativeFieldEvents[0] = NativeFieldEvent{EventID: 0xff}
	if _, ok := NativeFieldEventIDAt(st, 0, 0, 0); ok {
		t.Fatal("0xff event unexpectedly accepted")
	}
}
