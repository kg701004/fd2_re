package battle

import (
	"math/rand"
	"testing"
)

func TestExecuteNativeCommandDamageUsesRecoveredIDNine(t *testing.T) {
	actor := &Unit{Camp: Own, X: 0, Y: 0, HP: 20, MP: 3, OnField: true}
	confirmed := &Unit{Camp: Enemy, ClassID: 5, X: 1, Y: 0, HP: 100, OnField: true}
	other := &Unit{Camp: Enemy, ClassID: 5, X: 2, Y: 0, HP: 100, OnField: true}
	st := &State{W: 3, H: 1, Units: []*Unit{actor, confirmed, other}, NativeTargetFlags: make([]byte, 3), NativeCommandBook: []NativeCommandRecord{{ID: 0}}}
	// The executor requires the complete verified book rather than an invented
	// partial record; fill unused rows with exact sequential IDs for this unit
	// test, which only dispatches ID 9.
	for id := 1; id < 36; id++ {
		st.NativeCommandBook = append(st.NativeCommandBook, NativeCommandRecord{ID: id})
	}
	st.NativeCommandBook[9] = NativeCommandRecord{ID: 9, Damage: 50, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	results, err := st.ExecuteNativeCommandDamage(actor, confirmed, 9, map[int]int{5: 10}, rand.New(rand.NewSource(3)))
	if err != nil || len(results) != 1 || results[0].Target != confirmed || !results[0].Hit {
		t.Fatalf("results=%+v err=%v", results, err)
	}
	if actor.MP != 1 || !actor.Acted || confirmed.HP >= 100 || other.HP != 100 {
		t.Fatalf("mp/acted/hp actor=%d acted=%v confirmed=%d other=%d", actor.MP, actor.Acted, confirmed.HP, other.HP)
	}
}

func TestExecuteNativeCommandDamageFailsBeforeMPOnMissingResistance(t *testing.T) {
	actor := &Unit{Camp: Own, X: 0, Y: 0, HP: 20, MP: 3, OnField: true}
	target := &Unit{Camp: Enemy, ClassID: 99, X: 1, Y: 0, HP: 100, OnField: true}
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id].ID = id
	}
	book[9] = NativeCommandRecord{ID: 9, Damage: 50, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: book}
	if _, err := st.ExecuteNativeCommandDamage(actor, target, 9, map[int]int{}, rand.New(rand.NewSource(1))); err == nil || actor.MP != 3 || actor.Acted || target.HP != 100 {
		t.Fatalf("missing resistance mutated state: mp=%d acted=%v hp=%d err=%v", actor.MP, actor.Acted, target.HP, err)
	}
}

func TestExecuteNativeCommandDamageRejectsUnrecoveredIDOne(t *testing.T) {
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id].ID = id
	}
	book[1] = NativeCommandRecord{ID: 1, Damage: 120, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 1, TargetCode: 0}
	actor := &Unit{Camp: Own, X: 0, MP: 2, HP: 1, OnField: true}
	target := &Unit{Camp: Enemy, ClassID: 5, X: 1, HP: 200, OnField: true}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: book}
	if got, err := st.ExecuteNativeCommandDamage(actor, target, 1, map[int]int{5: 10}, rand.New(rand.NewSource(1))); err == nil || got != nil || actor.MP != 2 || actor.Acted || target.HP != 200 {
		t.Fatalf("unrecovered id mutated state: got=%+v err=%v", got, err)
	}
}

func TestExecuteNativeCommandDamageAcceptsRecoveredCompositorIDTen(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 3, X: 0, Y: 0}
	target := &Unit{Camp: Enemy, ClassID: 5, OnField: true, HP: 200, MaxHP: 200, X: 1, Y: 0}
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[10] = NativeCommandRecord{ID: 10, Damage: 100, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 1, TargetCode: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: book}

	if got, err := st.ExecuteNativeCommandDamage(actor, target, 10, map[int]int{5: 10}, rand.New(rand.NewSource(1))); err != nil || len(got) != 1 || !got[0].Hit || actor.MP != 2 || !actor.Acted || target.HP >= 200 {
		t.Fatalf("ID10 numeric route = %#v actor=%#v target=%#v err=%v", got, actor, target, err)
	}
}
