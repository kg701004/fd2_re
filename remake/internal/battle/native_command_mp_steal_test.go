package battle

import (
	"math/rand"
	"testing"
)

func mpStealBook() []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[36] = NativeCommandRecord{ID: 36, Damage: 40, Hit: 100, SelectionMode: 5, EffectMode: 0, MPCost: 20, TargetCode: 0}
	return book
}

func TestExecuteNativeCommandMPStealMovesMPOnHit(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, MP: 20, MaxMP: 100, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, ClassID: 5, HP: 100, MP: 100}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: mpStealBook()}

	got, err := st.ExecuteNativeCommandMPSteal(actor, target, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || !got[0].Hit || got[0].Stolen != 40 {
		t.Fatalf("result=%#v err=%v", got, err)
	}
	if target.MP != 100-40 {
		t.Fatalf("target.MP=%d, want %d", target.MP, 100-40)
	}
	if actor.MP != 20-1+40 { // Own pays flat-1 QoL MP, then gains the stolen 40
		t.Fatalf("actor.MP=%d, want %d", actor.MP, 20-1+40)
	}
	if !actor.Acted {
		t.Fatal("actor.Acted not set")
	}
}

func TestExecuteNativeCommandMPStealClampsToTargetMPAndCasterMaxMP(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, MP: 20, MaxMP: 25, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, ClassID: 5, HP: 100, MP: 5}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: mpStealBook()}

	got, err := st.ExecuteNativeCommandMPSteal(actor, target, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || !got[0].Hit {
		t.Fatalf("result=%#v err=%v", got, err)
	}
	// Book says steal 40, but target only has 5 MP and actor only has room
	// for 25-19=6 (after paying the flat-1 QoL cast cost) -- the smaller of
	// the two clamps wins.
	if got[0].Stolen != 5 {
		t.Fatalf("stolen=%d, want 5 (clamped by target's own MP)", got[0].Stolen)
	}
	if target.MP != 0 {
		t.Fatalf("target.MP=%d, want 0", target.MP)
	}
	if actor.MP != 24 { // 20-1+5
		t.Fatalf("actor.MP=%d, want 24", actor.MP)
	}
}

func TestExecuteNativeCommandMPStealEnemyPaysRawMPCost(t *testing.T) {
	// TargetCode 0 always requires an Enemy-camp target regardless of the
	// caster's own camp (NativeCommandTargetMatches); an Enemy caster still
	// needs an Enemy-camp target here to reach a valid candidate at all.
	actor := &Unit{Camp: Enemy, OnField: true, X: 0, Y: 0, HP: 100, MP: 20, MaxMP: 100, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, ClassID: 5, HP: 100, MP: 100}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: mpStealBook()}

	got, err := st.ExecuteNativeCommandMPSteal(actor, target, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || !got[0].Hit {
		t.Fatalf("result=%#v err=%v", got, err)
	}
	if actor.MP != 20-20+40 { // Enemy pays the raw 20 MP cost, no QoL discount
		t.Fatalf("actor.MP=%d, want %d", actor.MP, 20-20+40)
	}
}

func TestExecuteNativeCommandMPStealFailsClosedOnInsufficientMP(t *testing.T) {
	actor := &Unit{Camp: Enemy, OnField: true, X: 0, Y: 0, MP: 1}
	target := &Unit{Camp: Own, OnField: true, X: 1, Y: 0, ClassID: 5, HP: 100, MP: 30}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: mpStealBook()}

	if _, err := st.ExecuteNativeCommandMPSteal(actor, target, rand.New(rand.NewSource(1)), nil); err == nil || target.MP != 30 || actor.Acted {
		t.Fatalf("insufficient-MP cast mutated state: target.MP=%d acted=%v err=%v", target.MP, actor.Acted, err)
	}
}
