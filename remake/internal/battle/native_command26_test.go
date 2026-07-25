package battle

import (
	"math/rand"
	"testing"
)

func nativeCommandApplicationBook(id int) []NativeCommandRecord {
	book := make([]NativeCommandRecord, 36)
	for i := range book {
		book[i] = NativeCommandRecord{ID: i}
	}
	book[id] = NativeCommandRecord{ID: id, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	return book
}

func passingNativeApplicationRNG(t *testing.T) *rand.Rand {
	t.Helper()
	for seed := int64(0); seed < 1000; seed++ {
		r := rand.New(rand.NewSource(seed))
		if r.Intn(100) < 50 {
			return rand.New(rand.NewSource(seed))
		}
	}
	t.Fatal("no deterministic application RNG seed found")
	return nil
}

func TestExecuteNativeCommandApplicationUsesRawDurationAndFixedDamage(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 5, X: 0, Y: 0}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(26)}

	got, err := st.ExecuteNativeCommandApplication(actor, target, 26, passingNativeApplicationRNG(t))
	if err != nil || len(got) != 1 || !got[0].Applied || got[0].Damage != 10 || got[0].Duration < 2 || got[0].Duration > 5 {
		t.Fatalf("application = %#v, %v", got, err)
	}
	if target.HP != 10 || target.NativeTransient[3] != got[0].Duration || actor.MP != 3 || !actor.Acted {
		t.Fatalf("post application actor=%#v target=%#v", actor, target)
	}
}

func TestExecuteNativeCommandApplicationKeepsRawGateButConsumesSuccessfulCommand(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 5, X: 0, Y: 0}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, X: 1, Y: 0, NativeTransient: [6]byte{0, 0, 0, 4}}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(26)}

	got, err := st.ExecuteNativeCommandApplication(actor, target, 26, rand.New(rand.NewSource(1)))
	if err != nil || len(got) != 1 || got[0].Applied || target.HP != 20 || target.NativeTransient[3] != 4 || actor.MP != 3 || !actor.Acted {
		t.Fatalf("existing raw interval gate = %#v, actor=%#v target=%#v err=%v", got, actor, target, err)
	}
}

func TestExecuteNativeCommandApplicationSupportsRecoveredIDTwentyTwo(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 5, X: 0, Y: 0}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(22)}

	got, err := st.ExecuteNativeCommandApplication(actor, target, 22, passingNativeApplicationRNG(t))
	if err != nil || len(got) != 1 || !got[0].Applied || got[0].Offset != 0x27 || target.NativeTransient[5] != got[0].Duration || target.HP != 10 {
		t.Fatalf("ID22 application = %#v actor=%#v target=%#v err=%v", got, actor, target, err)
	}
}

func TestExecuteNativeCommandApplicationRejectsUnknownIDBeforeMutation(t *testing.T) {
	actor := &Unit{MP: 5}
	if _, err := (&State{}).ExecuteNativeCommandApplication(actor, nil, 25, rand.New(rand.NewSource(1))); err == nil || actor.MP != 5 || actor.Acted {
		t.Fatalf("unknown application ID must fail closed: actor=%#v err=%v", actor, err)
	}
}
