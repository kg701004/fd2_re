package battle

import (
	"math/rand"
	"testing"
)

func nativeCommand25Book() []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[25] = NativeCommandRecord{ID: 25, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 1}
	return book
}

func TestExecuteNativeCommand25ClearsOnlyFinalActedTargets(t *testing.T) {
	// Camp:Enemy is deliberate (see native_command0_test.go): locks in raw
	// native MP-debit math, unaffected by the remake-only Own/Ally QoL
	// MP discount.
	actor := &Unit{Camp: Enemy, OnField: true, HP: 10, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	confirmed := &Unit{Camp: Own, OnField: true, HP: 10, Acted: true, X: 1, Y: 0}
	other := &Unit{Camp: Own, OnField: true, HP: 10, Acted: false, X: 2, Y: 0}
	st := &State{W: 3, H: 1, Units: []*Unit{actor, confirmed, other}, NativeCompositionEventBytes: make([]byte, 3), NativeCommandBook: nativeCommand25Book()}

	got, err := st.ExecuteNativeCommand25(actor, confirmed, nil, nil)
	if err != nil || len(got) != 1 || got[0].Target != confirmed || !got[0].Cleared {
		t.Fatalf("result = %#v, %v; want confirmed acted clear", got, err)
	}
	if confirmed.Acted || !actor.Acted || other.Acted || actor.MP != 3 {
		t.Fatalf("post state actor=%#v confirmed=%#v other=%#v", actor, confirmed, other)
	}
}

// TestExecuteNativeCommand25AwardsExpOnlyWhenActedBitCleared covers the
// [0x53EC8] write point at 0x22C04 (doc13 §7's own-handler note, distinct
// from the shared 0x22af6/0x22d1b write points): levelFactor(target)*8 only
// for a target whose acted bit was actually cleared.
func TestExecuteNativeCommand25AwardsExpOnlyWhenActedBitCleared(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 10, MP: 5, Lv: 1, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	confirmed := &Unit{Camp: Own, OnField: true, HP: 10, Acted: true, Lv: 5, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, confirmed}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommand25Book()}

	got, err := st.ExecuteNativeCommand25(actor, confirmed, nil, rand.New(rand.NewSource(1)))
	if err != nil || len(got) != 1 || !got[0].Cleared {
		t.Fatalf("result = %#v, %v", got, err)
	}
	if actor.Exp != 40 { // levelFactor(Lv=5, ClassID=0)*8 = 40
		t.Fatalf("actor.Exp = %v, want 40", actor.Exp)
	}

	actor2 := &Unit{Camp: Own, OnField: true, HP: 10, MP: 5, Lv: 1, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	notActed := &Unit{Camp: Own, OnField: true, HP: 10, Acted: false, Lv: 5, X: 1, Y: 0}
	st2 := &State{W: 2, H: 1, Units: []*Unit{actor2, notActed}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommand25Book()}
	if _, err := st2.ExecuteNativeCommand25(actor2, notActed, nil, rand.New(rand.NewSource(1))); err != nil {
		t.Fatalf("unexpected err=%v", err)
	}
	if actor2.Exp != 0 {
		t.Fatalf("no target actually cleared, must not award exp: actor2.Exp = %v, want 0", actor2.Exp)
	}
}

func TestExecuteNativeCommand25FailsBeforeMPOnInvalidConfirmation(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 10, MP: 5, X: 0, Y: 0}
	confirmed := &Unit{Camp: Own, OnField: true, HP: 10, Acted: true, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, confirmed}, NativeCommandBook: nativeCommand25Book()}

	if _, err := st.ExecuteNativeCommand25(actor, confirmed, nil, nil); err == nil || actor.MP != 5 || actor.Acted || !confirmed.Acted {
		t.Fatalf("invalid native target data must fail before mutation: actor=%#v confirmed=%#v err=%v", actor, confirmed, err)
	}
}
