package battle

import (
	"math/rand"
	"testing"
)

func compoundBook() []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[32] = NativeCommandRecord{ID: 32, Damage: 800, Hit: 90, SelectionMode: 5, EffectMode: 3, MPCost: 76, TargetCode: 0}
	book[33] = NativeCommandRecord{ID: 33, Damage: 0, Hit: 0, SelectionMode: 5, EffectMode: 3, MPCost: 52, TargetCode: 1}
	book[34] = NativeCommandRecord{ID: 34, Damage: 0, Hit: 0, SelectionMode: 5, EffectMode: 3, MPCost: 28, TargetCode: 1}
	book[35] = NativeCommandRecord{ID: 35, Damage: 0, Hit: 0, SelectionMode: 4, EffectMode: 2, MPCost: 36, TargetCode: 0}
	return book
}

func TestExecuteNativeCommand32DealsBookDamage(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, MP: 80, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, HP: 1000, ClassID: 5}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: compoundBook()}

	got, _, err := st.ExecuteNativeCommand32(actor, target, map[int]int{5: 10}, 7, nil)
	if err != nil || len(got) != 1 || !got[0].Hit || got[0].Damage <= 0 {
		t.Fatalf("id32 result=%#v err=%v", got, err)
	}
	if target.HP >= 1000 || actor.MP != 79 || !actor.Acted {
		// MP: Own actor pays the QoL flat-1 discount, not the raw 76.
		t.Fatalf("id32 post state actor=%#v target=%#v", actor, target)
	}
}

func TestExecuteNativeCommand33Heals800(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, MP: 60, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Own, OnField: true, X: 1, Y: 0, HP: 10, MaxHP: 2000}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: compoundBook()}

	got, err := st.ExecuteNativeCommand33(actor, target, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || got[0].Restore.Actual < 720 || got[0].Restore.Actual > 800 {
		t.Fatalf("id33 result=%#v err=%v", got, err)
	}
	if target.HP != 10+got[0].Restore.Actual || actor.MP != 59 || !actor.Acted {
		t.Fatalf("id33 post state actor=%#v target=%#v", actor, target)
	}
}

func TestExecuteNativeCommand34AppliesTripleBuff(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, MP: 40, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Own, OnField: true, X: 1, Y: 0, HP: 100, MaxHP: 100}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: compoundBook()}

	got, err := st.ExecuteNativeCommand34(actor, target, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || got[0] != target {
		t.Fatalf("id34 result=%#v err=%v", got, err)
	}
	if target.BuffAPPct != 15 || target.BuffDPPct != 15 || target.BuffHit != 15 || target.BuffEV != 15 || target.BuffTurns <= 0 {
		t.Fatalf("id34 buff state target=%#v", target)
	}
	if actor.MP != 39 || !actor.Acted {
		t.Fatalf("id34 actor state=%#v", actor)
	}
}

func TestExecuteNativeCommand35AppliesThreeStatusRolls(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, MP: 40, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, HP: 1000, ClassID: 5}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: compoundBook()}

	got, err := st.ExecuteNativeCommand35(actor, target, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 3 {
		t.Fatalf("id35 result=%#v err=%v", got, err)
	}
	wantOffsets := map[int]bool{0x25: true, 0x27: true, 0x26: true}
	for _, r := range got {
		if !wantOffsets[r.Offset] {
			t.Fatalf("id35 unexpected offset in result=%#v", r)
		}
	}
	if actor.MP != 39 || !actor.Acted {
		t.Fatalf("id35 actor state=%#v", actor)
	}
}

func TestExecuteNativeCommand33FailsClosedOnInsufficientMP(t *testing.T) {
	actor := &Unit{Camp: Enemy, OnField: true, X: 0, Y: 0, MP: 1}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, HP: 10, MaxHP: 2000}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: compoundBook()}

	if _, err := st.ExecuteNativeCommand33(actor, target, rand.New(rand.NewSource(1)), nil); err == nil || target.HP != 10 || actor.Acted {
		// Camp:Enemy deliberately keeps the raw 52 MP cost (no QoL discount),
		// so 1 MP must fail closed here.
		t.Fatalf("insufficient-MP id33 mutated state: actor=%#v target=%#v", actor, target)
	}
}
