package battle

import (
	"math/rand"
	"testing"
)

type countingZeroSource struct {
	draws int
}

func (s *countingZeroSource) Int63() int64 {
	s.draws++
	return 0
}

func (s *countingZeroSource) Seed(int64) {}

func nativeCommandApplicationBook(id int) []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
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

func TestExecuteNativeCommandApplicationUsesThreeRNGDrawsAndNativeDamage(t *testing.T) {
	// Camp:Enemy is deliberate (see native_command0_test.go): locks in raw
	// native MP-debit math, unaffected by the remake-only Own/Ally QoL
	// MP discount.
	actor := &Unit{Camp: Enemy, OnField: true, HP: 20, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(26)}

	got, err := st.ExecuteNativeCommandApplication(actor, target, 26, passingNativeApplicationRNG(t), nil)
	if err != nil || len(got) != 1 || !got[0].Applied || got[0].Damage != 9 || got[0].Duration < 2 || got[0].Duration > 5 {
		t.Fatalf("application = %#v, %v", got, err)
	}
	if target.HP != 11 || target.NativeTransient[3] != got[0].Duration || actor.MP != 3 || !actor.Acted {
		t.Fatalf("post application actor=%#v target=%#v", actor, target)
	}
}

func TestExecuteNativeCommandApplicationConsumesGateDamageMarkerDraws(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(22)}
	source := &countingZeroSource{}

	got, err := st.ExecuteNativeCommandApplication(actor, target, 22, rand.New(source), nil)
	if err != nil || len(got) != 1 || !got[0].Applied {
		t.Fatalf("application = %#v, %v", got, err)
	}
	if source.draws != 3 || got[0].Damage != 9 || got[0].Duration != 2 {
		t.Fatalf("draws=%d result=%+v", source.draws, got[0])
	}
}

func TestExecuteNativeCommandApplicationKeepsRawGateButConsumesSuccessfulCommand(t *testing.T) {
	// Camp:Enemy is deliberate (see native_command0_test.go): locks in raw
	// native MP-debit math, unaffected by the remake-only Own/Ally QoL
	// MP discount.
	actor := &Unit{Camp: Enemy, OnField: true, HP: 20, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, X: 1, Y: 0, NativeTransient: [6]byte{0, 0, 0, 4}}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(26)}

	got, err := st.ExecuteNativeCommandApplication(actor, target, 26, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || got[0].Applied || target.HP != 20 || target.NativeTransient[3] != 4 || actor.MP != 3 || !actor.Acted {
		t.Fatalf("existing raw interval gate = %#v, actor=%#v target=%#v err=%v", got, actor, target, err)
	}
}

func TestExecuteNativeCommandApplicationSupportsRecoveredIDTwentyTwo(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(22)}

	got, err := st.ExecuteNativeCommandApplication(actor, target, 22, passingNativeApplicationRNG(t), nil)
	if err != nil || len(got) != 1 || !got[0].Applied || got[0].Offset != 0x27 || target.NativeTransient[5] != got[0].Duration || target.HP != 11 {
		t.Fatalf("ID22 application = %#v actor=%#v target=%#v err=%v", got, actor, target, err)
	}
}

// TestExecuteNativeCommandApplicationAwardsExpOnlyWhenApplied covers the
// [0x53EC8] write point at 0x22d1b (doc13 §7 / doc27 §5.1.A): levelFactor
// (target)*8 only for a target the RNG gate + raw-interval check actually let
// through, never for the gated-out no-op route.
func TestExecuteNativeCommandApplicationAwardsExpOnlyWhenApplied(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 5, Lv: 1, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, Lv: 5, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(26)}

	got, err := st.ExecuteNativeCommandApplication(actor, target, 26, passingNativeApplicationRNG(t), nil)
	if err != nil || len(got) != 1 || !got[0].Applied {
		t.Fatalf("application = %#v, %v", got, err)
	}
	if actor.Exp != 40 { // levelFactor(Lv=5, ClassID=2)*8 = 40
		t.Fatalf("actor.Exp = %v, want 40", actor.Exp)
	}

	actor2 := &Unit{Camp: Own, OnField: true, HP: 20, MP: 5, Lv: 1, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target2 := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 20, Lv: 5, X: 1, Y: 0, NativeTransient: [6]byte{0, 0, 0, 4}}
	st2 := &State{W: 2, H: 1, Units: []*Unit{actor2, target2}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandApplicationBook(26)}
	if _, err := st2.ExecuteNativeCommandApplication(actor2, target2, 26, rand.New(rand.NewSource(1)), nil); err != nil {
		t.Fatalf("unexpected err=%v", err)
	}
	if actor2.Exp != 0 {
		t.Fatalf("gated-out application must not award exp: actor2.Exp = %v, want 0", actor2.Exp)
	}
}

func TestExecuteNativeCommandApplicationRejectsUnknownIDBeforeMutation(t *testing.T) {
	actor := &Unit{MP: 5}
	if _, err := (&State{}).ExecuteNativeCommandApplication(actor, nil, 25, rand.New(rand.NewSource(1)), nil); err == nil || actor.MP != 5 || actor.Acted {
		t.Fatalf("unknown application ID must fail closed: actor=%#v err=%v", actor, err)
	}
}
