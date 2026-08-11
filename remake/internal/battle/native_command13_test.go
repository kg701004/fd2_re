package battle

import (
	"math/rand"
	"testing"
)

func nativeCommandHealBook(id int) []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for i := range book {
		book[i] = NativeCommandRecord{ID: i}
	}
	book[id] = NativeCommandRecord{ID: id, Damage: 70, SelectionMode: 1, EffectMode: 0, MPCost: 3, TargetCode: 1}
	return book
}

func TestExecuteNativeCommandHealUsesSelectedRecordAndCapsHP(t *testing.T) {
	// Camp:Enemy is deliberate (see native_command0_test.go): locks in raw
	// native MP-debit math, unaffected by the remake-only Own/Ally QoL
	// MP discount.
	actor := &Unit{Camp: Enemy, OnField: true, HP: 20, MP: 5, X: 0, Y: 0}
	target := &Unit{Camp: Own, OnField: true, HP: 40, MaxHP: 100, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandHealBook(13)}

	got, err := st.ExecuteNativeCommandHeal(actor, target, 13, rand.New(rand.NewSource(2)))
	if err != nil || len(got) != 1 || got[0].Target != target || got[0].Restore.Rolled < 63 || got[0].Restore.Rolled > 69 {
		t.Fatalf("heal = %#v, %v", got, err)
	}
	if target.HP != 100 || got[0].Restore.Actual != 60 || actor.MP != 2 || !actor.Acted {
		t.Fatalf("post heal actor=%#v target=%#v result=%#v", actor, target, got[0])
	}
}

func TestExecuteNativeCommandHealRejectsFamilyBoundaryBeforeMutation(t *testing.T) {
	actor := &Unit{MP: 5}
	if _, err := (&State{}).ExecuteNativeCommandHeal(actor, nil, 12, rand.New(rand.NewSource(1))); err == nil || actor.MP != 5 || actor.Acted {
		t.Fatalf("non-heal ID must fail closed: actor=%#v err=%v", actor, err)
	}
}
