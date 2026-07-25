package battle

import (
	"math/rand"
	"testing"
)

func nativeCommand24Book() []NativeCommandRecord {
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	// Raw record24 is 00 00 00 05 01 16 00: selection=5, effect=1,
	// MP=22, target-code=0.  Damage/hit are intentionally unused here.
	book[24] = NativeCommandRecord{ID: 24, SelectionMode: 5, EffectMode: 1, MPCost: 22, TargetCode: 0}
	return book
}

func TestExecuteNativeCommand24UsesDerivedStatsAndOneMPDebit(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, AP: 100, MP: 30}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, DP: 20, HP: 200}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: nativeCommand24Book()}

	got, err := st.ExecuteNativeCommand24(actor, target, rand.New(rand.NewSource(2)))
	if err != nil || len(got) != 1 || got[0].Target != target || got[0].Amount != 130 || got[0].Damage < 117 || got[0].Damage > 129 {
		t.Fatalf("ID24 result=%#v err=%v", got, err)
	}
	if target.HP != 200-got[0].Damage || actor.MP != 8 || !actor.Acted {
		t.Fatalf("ID24 state actor=%#v target=%#v result=%#v", actor, target, got[0])
	}
}

func TestExecuteNativeCommand24RejectsInvalidBookBeforeMutation(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, MP: 30}
	target := &Unit{Camp: Enemy, OnField: true, HP: 100}
	book := nativeCommand24Book()
	book[24].ID = 0
	st := &State{W: 1, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: []byte{0}, NativeCommandBook: book}
	if _, err := st.ExecuteNativeCommand24(actor, target, rand.New(rand.NewSource(1))); err == nil || actor.MP != 30 || actor.Acted || target.HP != 100 {
		t.Fatalf("invalid ID24 book mutated state actor=%#v target=%#v err=%v", actor, target, err)
	}
}
