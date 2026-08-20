package battle

import (
	"math/rand"
	"testing"
)

func nativeCommandClearRestoreBook(id int) []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for i := range book {
		book[i] = NativeCommandRecord{ID: i}
	}
	book[10] = NativeCommandRecord{ID: 10, Damage: 100}
	book[id] = NativeCommandRecord{ID: id, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 1}
	return book
}

func TestExecuteNativeCommandClearRestoreUsesRecordTenAndRawFlag(t *testing.T) {
	// Camp:Enemy is deliberate (see native_command0_test.go): locks in raw
	// native MP-debit math, unaffected by the remake-only Own/Ally QoL
	// MP discount.
	actor := &Unit{Camp: Enemy, OnField: true, HP: 10, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Own, OnField: true, HP: 1, MaxHP: 100, X: 1, Y: 0, NativeTransient: [6]byte{0, 0, 0, 3}}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandClearRestoreBook(20)}

	got, err := st.ExecuteNativeCommandClearRestore(actor, target, 20, rand.New(rand.NewSource(2)), nil)
	if err != nil || len(got) != 1 || !got[0].Cleared || got[0].Offset != 0x25 || got[0].Restore.Rolled < 90 || got[0].Restore.Rolled > 99 {
		t.Fatalf("clear/restore = %#v, %v", got, err)
	}
	if target.NativeTransient[3] != 0 || target.HP != 1+got[0].Restore.Actual || actor.MP != 3 || !actor.Acted {
		t.Fatalf("post clear/restore actor=%#v target=%#v", actor, target)
	}
}

func TestExecuteNativeCommandClearRestoreConsumesCommandWhenFlagEmpty(t *testing.T) {
	// Camp:Enemy is deliberate (see native_command0_test.go): locks in raw
	// native MP-debit math, unaffected by the remake-only Own/Ally QoL
	// MP discount.
	actor := &Unit{Camp: Enemy, OnField: true, HP: 10, MP: 5, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Own, OnField: true, HP: 10, MaxHP: 20, X: 1, Y: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandClearRestoreBook(21)}

	got, err := st.ExecuteNativeCommandClearRestore(actor, target, 21, rand.New(rand.NewSource(1)), nil)
	if err != nil || len(got) != 1 || got[0].Cleared || target.HP != 10 || actor.MP != 3 || !actor.Acted {
		t.Fatalf("empty-flag route = %#v actor=%#v target=%#v err=%v", got, actor, target, err)
	}
}

// TestExecuteNativeCommandClearRestoreAwardsExpOnlyWhenCleared covers the
// [0x53EC8] write point at 0x22af6 (doc13 §7 / doc27 §5.1.A): levelFactor
// (target)*4 -- half the application family's rate below -- only for a
// target whose raw interval was actually cleared, never for the no-op route.
func TestExecuteNativeCommandClearRestoreAwardsExpOnlyWhenCleared(t *testing.T) {
	// target.Camp must stay non-Enemy (Own here): nativeCommandClearRestoreBook's
	// TargetCode:1 resolves to "candidate.Camp != Enemy" (see
	// NativeCommandTargetMatches), independent of actor.Camp. actor.Camp is
	// Own so GainExp (Own/Ally-only) actually applies below.
	actor := &Unit{Camp: Own, OnField: true, HP: 10, MP: 5, Lv: 1, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Own, OnField: true, HP: 1, MaxHP: 100, Lv: 5, X: 1, Y: 0, NativeTransient: [6]byte{0, 0, 0, 3}}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandClearRestoreBook(20)}

	got, err := st.ExecuteNativeCommandClearRestore(actor, target, 20, rand.New(rand.NewSource(2)), nil)
	if err != nil || len(got) != 1 || !got[0].Cleared {
		t.Fatalf("clear/restore = %#v, %v", got, err)
	}
	if actor.Exp != 20 { // levelFactor(Lv=5, ClassID=0)*4 = 20
		t.Fatalf("actor.Exp = %v, want 20", actor.Exp)
	}

	actor2 := &Unit{Camp: Own, OnField: true, HP: 10, MP: 5, Lv: 1, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target2 := &Unit{Camp: Own, OnField: true, HP: 10, MaxHP: 20, Lv: 5, X: 1, Y: 0}
	st2 := &State{W: 2, H: 1, Units: []*Unit{actor2, target2}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: nativeCommandClearRestoreBook(21)}
	if _, err := st2.ExecuteNativeCommandClearRestore(actor2, target2, 21, rand.New(rand.NewSource(1)), nil); err != nil {
		t.Fatalf("unexpected err=%v", err)
	}
	if actor2.Exp != 0 {
		t.Fatalf("no-op clear route must not award exp: actor2.Exp = %v, want 0", actor2.Exp)
	}
}

func TestApplyNativeCommandRestoreClampsStateButReportsRolledAmount(t *testing.T) {
	target := &Unit{HP: 95, MaxHP: 100}
	got, err := ApplyNativeCommandRestore(target, 100, rand.New(rand.NewSource(3)))
	if err != nil || got.Rolled < 90 || got.Rolled > 99 || got.Actual != 5 || target.HP != 100 {
		t.Fatalf("restore cap = %#v target=%#v err=%v", got, target, err)
	}
}
