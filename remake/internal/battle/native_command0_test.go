package battle

import (
	"math/rand"
	"testing"
)

func TestExecuteNativeCommand0UsesTwoStageTargetsAndOneMPDebit(t *testing.T) {
	actor := &Unit{Camp: Own, X: 0, Y: 0, HP: 20, MP: 3, OnField: true}
	confirmed := &Unit{Camp: Enemy, ClassID: 5, X: 1, Y: 0, HP: 100, OnField: true}
	other := &Unit{Camp: Enemy, ClassID: 5, X: 2, Y: 0, HP: 100, OnField: true}
	st := &State{W: 3, H: 1, Units: []*Unit{actor, confirmed, other}, NativeTargetFlags: make([]byte, 3), NativeCommandBook: []NativeCommandRecord{{ID: 0, Damage: 50, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}}}
	// The executor requires the complete verified book rather than an invented
	// partial record; fill unused rows with exact sequential IDs for this unit
	// test, which only dispatches ID 0.
	for id := 1; id < 36; id++ {
		st.NativeCommandBook = append(st.NativeCommandBook, NativeCommandRecord{ID: id})
	}
	results, err := st.ExecuteNativeCommand0(actor, confirmed, map[int]int{5: 10}, rand.New(rand.NewSource(3)))
	if err != nil || len(results) != 1 || results[0].Target != confirmed || !results[0].Hit {
		t.Fatalf("results=%+v err=%v", results, err)
	}
	if actor.MP != 1 || confirmed.HP >= 100 || other.HP != 100 {
		t.Fatalf("mp/hp actor=%d confirmed=%d other=%d", actor.MP, confirmed.HP, other.HP)
	}
}

func TestExecuteNativeCommand0FailsBeforeMPOnMissingResistance(t *testing.T) {
	actor := &Unit{Camp: Own, X: 0, Y: 0, HP: 20, MP: 3, OnField: true}
	target := &Unit{Camp: Enemy, ClassID: 99, X: 1, Y: 0, HP: 100, OnField: true}
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id].ID = id
	}
	book[0] = NativeCommandRecord{ID: 0, Damage: 50, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: book}
	if _, err := st.ExecuteNativeCommand0(actor, target, map[int]int{}, rand.New(rand.NewSource(1))); err == nil || actor.MP != 3 || target.HP != 100 {
		t.Fatalf("missing resistance mutated state: mp=%d hp=%d err=%v", actor.MP, target.HP, err)
	}
}
