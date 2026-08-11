package battle

import "testing"

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
	actor := &Unit{Camp: Enemy, OnField: true, HP: 10, MP: 5, X: 0, Y: 0}
	confirmed := &Unit{Camp: Own, OnField: true, HP: 10, Acted: true, X: 1, Y: 0}
	other := &Unit{Camp: Own, OnField: true, HP: 10, Acted: false, X: 2, Y: 0}
	st := &State{W: 3, H: 1, Units: []*Unit{actor, confirmed, other}, NativeCompositionEventBytes: make([]byte, 3), NativeCommandBook: nativeCommand25Book()}

	got, err := st.ExecuteNativeCommand25(actor, confirmed)
	if err != nil || len(got) != 1 || got[0].Target != confirmed || !got[0].Cleared {
		t.Fatalf("result = %#v, %v; want confirmed acted clear", got, err)
	}
	if confirmed.Acted || !actor.Acted || other.Acted || actor.MP != 3 {
		t.Fatalf("post state actor=%#v confirmed=%#v other=%#v", actor, confirmed, other)
	}
}

func TestExecuteNativeCommand25FailsBeforeMPOnInvalidConfirmation(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 10, MP: 5, X: 0, Y: 0}
	confirmed := &Unit{Camp: Own, OnField: true, HP: 10, Acted: true, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, confirmed}, NativeCommandBook: nativeCommand25Book()}

	if _, err := st.ExecuteNativeCommand25(actor, confirmed); err == nil || actor.MP != 5 || actor.Acted || !confirmed.Acted {
		t.Fatalf("invalid native target data must fail before mutation: actor=%#v confirmed=%#v err=%v", actor, confirmed, err)
	}
}
