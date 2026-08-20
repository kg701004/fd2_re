package battle

import (
	"math/rand"
	"testing"
)

func nativeCommand23Book() []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[23] = NativeCommandRecord{ID: 23, MPCost: 6}
	return book
}

func TestExecuteNativeCommand23RelocatesTargetAndDebitsMP(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 10, MP: 10, Lv: 1, X: 0, Y: 0}
	target := &Unit{Camp: Own, OnField: true, HP: 10, Lv: 5, X: 1, Y: 0, Dir: 2}
	st := &State{W: 5, H: 5, Units: []*Unit{actor, target}, NativeCommandBook: nativeCommand23Book()}

	got, err := st.ExecuteNativeCommand23(actor, target, 4, 4, rand.New(rand.NewSource(1)))
	if err != nil || !got.Relocated || got.ToX != 4 || got.ToY != 4 || got.FromX != 1 || got.FromY != 0 {
		t.Fatalf("relocation result = %#v, err=%v", got, err)
	}
	if target.X != 4 || target.Y != 4 || target.Dir != 2 {
		t.Fatalf("target post-relocation = %#v, want X=4 Y=4 Dir preserved", target)
	}
	// actor.Camp==Own pays the remake-only flat-1-MP QoL rate (see
	// NativeCommandMPCostFor), not the raw book cost of 6.
	if actor.MP != 9 || !actor.Acted {
		t.Fatalf("actor post-cast = %#v, want MP=9 Acted=true", actor)
	}
	if actor.Exp != 50 { // levelFactor(Lv=5, ClassID=0)*10 = 50
		t.Fatalf("actor.Exp = %v, want 50", actor.Exp)
	}
}

func TestExecuteNativeCommand23RejectsOccupiedDestinationBeforeMP(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 10, MP: 10, X: 0, Y: 0}
	target := &Unit{Camp: Own, OnField: true, HP: 10, X: 1, Y: 0}
	blocker := &Unit{Camp: Enemy, OnField: true, HP: 10, X: 4, Y: 4}
	st := &State{W: 5, H: 5, Units: []*Unit{actor, target, blocker}, NativeCommandBook: nativeCommand23Book()}

	if _, err := st.ExecuteNativeCommand23(actor, target, 4, 4, rand.New(rand.NewSource(1))); err == nil || actor.MP != 10 || actor.Acted || target.X != 1 {
		t.Fatalf("occupied destination must fail before mutation: actor=%#v target=%#v err=%v", actor, target, err)
	}
}

func TestExecuteNativeCommand23RejectsOutOfBoundsDestination(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 10, MP: 10, X: 0, Y: 0}
	target := &Unit{Camp: Own, OnField: true, HP: 10, X: 1, Y: 0}
	st := &State{W: 5, H: 5, Units: []*Unit{actor, target}, NativeCommandBook: nativeCommand23Book()}

	if _, err := st.ExecuteNativeCommand23(actor, target, 5, 0, rand.New(rand.NewSource(1))); err == nil || actor.MP != 10 || actor.Acted {
		t.Fatalf("out-of-bounds destination must fail before mutation: actor=%#v err=%v", actor, err)
	}
}

func TestExecuteNativeCommand23FailsClosedOnMissingRecord(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 10, MP: 10, X: 0, Y: 0}
	target := &Unit{Camp: Own, OnField: true, HP: 10, X: 1, Y: 0}
	st := &State{W: 5, H: 5, Units: []*Unit{actor, target}}

	if _, err := st.ExecuteNativeCommand23(actor, target, 4, 4, rand.New(rand.NewSource(1))); err == nil {
		t.Fatal("missing native command book must fail closed")
	}
}
