package battle

import (
	"math/rand"
	"testing"
)

func nativeCommandModifierBook(id int) []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for i := range book {
		book[i] = NativeCommandRecord{ID: i}
	}
	book[id] = NativeCommandRecord{ID: id, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	return book
}

func TestExecuteNativeCommandModifierID17BumpsAPByTruncatedFifteenPercent(t *testing.T) {
	actor := &Unit{Camp: Enemy, OnField: true, HP: 20, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, HP: 20, AP: 100, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandModifierBook(17)}

	got, err := st.ExecuteNativeCommandModifier(actor, target, 17, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || !got[0].Applied || got[0].Offset != 0x22 || got[0].Delta != 16 {
		t.Fatalf("ID17 modifier = %#v, err=%v", got, err)
	}
	if target.AP != 116 { // trunc(100*0.15+1) = trunc(16.0) = 16
		t.Fatalf("target.AP = %d, want 116", target.AP)
	}
	if target.NativeTransient[0] != got[0].Duration || got[0].Duration < 2 || got[0].Duration > 5 {
		t.Fatalf("target.NativeTransient[0] = %d, want duration %d in [2,5]", target.NativeTransient[0], got[0].Duration)
	}
	if actor.MP != 3 || !actor.Acted {
		t.Fatalf("actor post-cast = %#v", actor)
	}
}

func TestExecuteNativeCommandModifierID18BumpsDP(t *testing.T) {
	actor := &Unit{Camp: Enemy, OnField: true, HP: 20, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, HP: 20, DP: 40, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandModifierBook(18)}

	got, err := st.ExecuteNativeCommandModifier(actor, target, 18, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || !got[0].Applied || got[0].Offset != 0x23 || got[0].Delta != 7 {
		t.Fatalf("ID18 modifier = %#v, err=%v", got, err)
	}
	if target.DP != 47 { // trunc(40*0.15+1) = trunc(7.0) = 7
		t.Fatalf("target.DP = %d, want 47", target.DP)
	}
	if target.NativeTransient[1] != got[0].Duration {
		t.Fatalf("target.NativeTransient[1] = %d, want %d", target.NativeTransient[1], got[0].Duration)
	}
}

func TestExecuteNativeCommandModifierID19AddsFlatFifteenToHitAndEV(t *testing.T) {
	actor := &Unit{Camp: Enemy, OnField: true, HP: 20, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, HP: 20, HIT: 70, EV: 10, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandModifierBook(19)}

	got, err := st.ExecuteNativeCommandModifier(actor, target, 19, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || !got[0].Applied || got[0].Offset != 0x24 {
		t.Fatalf("ID19 modifier = %#v, err=%v", got, err)
	}
	if target.HIT != 85 || target.EV != 25 {
		t.Fatalf("target HIT/EV = %d/%d, want 85/25", target.HIT, target.EV)
	}
	if target.NativeTransient[2] != got[0].Duration {
		t.Fatalf("target.NativeTransient[2] = %d, want %d", target.NativeTransient[2], got[0].Duration)
	}
}

func TestExecuteNativeCommandModifierSkipsAlreadyActiveTarget(t *testing.T) {
	actor := &Unit{Camp: Enemy, OnField: true, HP: 20, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, OnField: true, HP: 20, AP: 100, X: 1, Y: 0, NativeTransient: [6]byte{4}}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandModifierBook(17)}

	got, err := st.ExecuteNativeCommandModifier(actor, target, 17, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || got[0].Applied || target.AP != 100 || target.NativeTransient[0] != 4 {
		t.Fatalf("already-active target must be a no-op: got=%#v target=%#v err=%v", got, target, err)
	}
	if actor.MP != 3 || !actor.Acted {
		t.Fatal("command must still consume MP/turn even when every target is already buffed")
	}
}

func TestExecuteNativeCommandModifierRejectsUnknownIDBeforeMutation(t *testing.T) {
	actor := &Unit{MP: 5}
	if _, err := (&State{}).ExecuteNativeCommandModifier(actor, nil, 16, rand.New(rand.NewSource(1)), nil); err == nil || actor.MP != 5 || actor.Acted {
		t.Fatalf("unknown modifier ID must fail closed: actor=%#v err=%v", actor, err)
	}
}
