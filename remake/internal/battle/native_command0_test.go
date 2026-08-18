package battle

import "testing"

func TestExecuteBoundNativeCommand0UsesTwoStageTargetsAndOneMPDebit(t *testing.T) {
	// Camp:Enemy is deliberate here (not a statement about who casts this
	// command narratively): this test locks in the raw native MP-debit math,
	// and the remake-only QoL flat-1-MP discount (user request) only applies
	// to Own/Ally, so an Own actor would no longer exercise the original
	// 2-MP deduction this test verifies.
	actor := &Unit{Camp: Enemy, X: 0, Y: 0, HP: 20, MP: 3, OnField: true, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	confirmed := &Unit{Camp: Enemy, ClassID: 5, X: 1, Y: 0, HP: 100, OnField: true}
	other := &Unit{Camp: Enemy, ClassID: 5, X: 2, Y: 0, HP: 100, OnField: true}
	st := &State{W: 3, H: 1, Units: []*Unit{actor, confirmed, other}, NativeCompositionEventBytes: make([]byte, 3), NativeCommandBook: []NativeCommandRecord{{ID: 0}}}
	// The executor requires the complete verified book rather than an invented
	// partial record; fill unused rows with exact sequential IDs for this unit
	// test, which only dispatches ID 0.
	for id := 1; id < NativeCommandRecordCount; id++ {
		st.NativeCommandBook = append(st.NativeCommandBook, NativeCommandRecord{ID: id})
	}
	st.NativeCommandBook[0] = NativeCommandRecord{ID: 0, Damage: 50, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	st.NativeCommandResistances = map[int]int{5: 10}
	results, state, err := st.ExecuteBoundNativeCommand0(actor, confirmed, 3, nil)
	if err != nil || len(results) != 1 || results[0].Target != confirmed || !results[0].Hit {
		t.Fatalf("results=%+v state=%#x err=%v", results, state, err)
	}
	if actor.MP != 1 || !actor.Acted || confirmed.HP >= 100 || other.HP != 100 {
		t.Fatalf("mp/acted/hp actor=%d acted=%v confirmed=%d other=%d", actor.MP, actor.Acted, confirmed.HP, other.HP)
	}
}

func TestExecuteBoundNativeCommand0FailsBeforeMPOnMissingResistance(t *testing.T) {
	actor := &Unit{Camp: Own, X: 0, Y: 0, HP: 20, MP: 3, OnField: true}
	target := &Unit{Camp: Enemy, ClassID: 99, X: 1, Y: 0, HP: 100, OnField: true}
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id].ID = id
	}
	book[0] = NativeCommandRecord{ID: 0, Damage: 50, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: book}
	if _, _, err := st.ExecuteBoundNativeCommand0(actor, target, 1, nil); err == nil || actor.MP != 3 || actor.Acted || target.HP != 100 {
		t.Fatalf("missing resistance mutated state: mp=%d acted=%v hp=%d err=%v", actor.MP, actor.Acted, target.HP, err)
	}
}

func TestNativeCommandHitForOverridesID9OnlyForOwnAlly(t *testing.T) {
	own := &Unit{Camp: Own}
	ally := &Unit{Camp: Ally}
	enemy := &Unit{Camp: Enemy}
	if got := NativeCommandHitFor(own, 9, 50); got != 100 {
		t.Fatalf("Own casting id9: hit=%d, want 100", got)
	}
	if got := NativeCommandHitFor(ally, 9, 50); got != 100 {
		t.Fatalf("Ally casting id9: hit=%d, want 100", got)
	}
	if got := NativeCommandHitFor(enemy, 9, 50); got != 50 {
		t.Fatalf("Enemy casting id9: hit=%d, want unchanged raw 50", got)
	}
	// Every other command ID must stay untouched regardless of caster camp.
	if got := NativeCommandHitFor(own, 0, 90); got != 90 {
		t.Fatalf("Own casting id0: hit=%d, want unchanged raw 90", got)
	}
	if got := NativeCommandHitFor(nil, 9, 50); got != 50 {
		t.Fatalf("nil caster: hit=%d, want unchanged raw 50", got)
	}
}

func TestExecuteNativeCommandDamageAcceptsRecoveredIDOne(t *testing.T) {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id].ID = id
	}
	book[1] = NativeCommandRecord{ID: 1, Damage: 120, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 1, TargetCode: 0}
	actor := &Unit{Camp: Own, X: 0, MP: 2, HP: 1, OnField: true, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, ClassID: 5, X: 1, HP: 200, OnField: true}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: book}
	if got, _, err := st.ExecuteNativeCommandDamage(actor, target, 1, map[int]int{5: 10}, 1, nil); err != nil || len(got) != 1 || actor.MP != 1 || !actor.Acted || target.HP >= 200 {
		t.Fatalf("got=%+v err=%v", got, err)
	}
}

func TestExecuteNativeCommandDamageAcceptsRecoveredCompositorIDTen(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 3, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	target := &Unit{Camp: Enemy, ClassID: 5, OnField: true, HP: 200, MaxHP: 200, X: 1, Y: 0}
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[10] = NativeCommandRecord{ID: 10, Damage: 100, Hit: 100, SelectionMode: 1, EffectMode: 0, MPCost: 1, TargetCode: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: book}

	if got, _, err := st.ExecuteNativeCommandDamage(actor, target, 10, map[int]int{5: 10}, 1, nil); err != nil || len(got) != 1 || !got[0].Hit || actor.MP != 2 || !actor.Acted || target.HP >= 200 {
		t.Fatalf("ID10 numeric route = %#v actor=%#v target=%#v err=%v", got, actor, target, err)
	}
}

// TestExecuteNativeCommandDamageSelectionModeZeroUsesActorOrigin covers the
// 2026-08-17 fix for IDs 10..12's real record shape (SelectionMode==0, a
// budget-0 flood fill whose only reachable cell is the caster's own): the
// generic two-stage NativeCommandEffectTargets requires confirmed to be a
// candidate within the ACTOR's own SelectionMode area, which no real
// opposing target can ever satisfy when that area is just the actor's own
// cell -- every AI-chosen SelectionMode==0 cast failed with "confirmed unit
// is not a native command candidate" (see 58-remake-live-verification-log.md's
// #113 section, and 0x21548's disassembly showing no per-candidate
// confirmation step at all for this family). nativeSelfOriginCommandTargets
// instead resolves EffectMode's area directly from the actor's cell and only
// fail-closed-checks that confirmed is one of the results.
func TestExecuteNativeCommandDamageSelectionModeZeroUsesActorOrigin(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 90, X: 5, Y: 5, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	// EffectMode=1: a plus-shaped area one cell out from actor's own cell.
	// Neither target stands ON actor's cell (the old stage-1 check's only
	// possible candidate), only within EffectMode's reach from it.
	near := &Unit{Camp: Enemy, ClassID: 5, OnField: true, HP: 200, MaxHP: 200, X: 6, Y: 5}
	far := &Unit{Camp: Enemy, ClassID: 5, OnField: true, HP: 200, MaxHP: 200, X: 8, Y: 5}
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[12] = NativeCommandRecord{ID: 12, Damage: 340, Hit: 90, SelectionMode: 0, EffectMode: 1, MPCost: 80, TargetCode: 0}
	st := &State{W: 12, H: 12, Units: []*Unit{actor, near, far}, NativeCompositionEventBytes: make([]byte, 144), NativeCommandBook: book}

	got, _, err := st.ExecuteNativeCommandDamage(actor, near, 12, map[int]int{5: 10}, 1, nil)
	if err != nil {
		t.Fatalf("SelectionMode==0 with a real in-range confirmed target was rejected: %v", err)
	}
	if len(got) != 1 || got[0].Target != near {
		t.Fatalf("expected exactly near in the effect list, got %#v", got)
	}
	if far.HP != 200 {
		t.Fatalf("far target outside EffectMode's reach must be untouched, got HP=%d", far.HP)
	}
	if !actor.Acted {
		t.Fatal("actor.Acted not set")
	}
}

// TestExecuteNativeCommandDamageSelectionModeZeroRejectsUnconfirmedTarget
// keeps the fail-closed contract: a "confirmed" unit outside EffectMode's
// reach from the actor's own cell must still be rejected, not silently
// accepted just because SelectionMode==0 skips the old stage-1 check.
func TestExecuteNativeCommandDamageSelectionModeZeroRejectsUnconfirmedTarget(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, HP: 20, MP: 90, X: 5, Y: 5, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	far := &Unit{Camp: Enemy, ClassID: 5, OnField: true, HP: 200, MaxHP: 200, X: 8, Y: 5}
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[12] = NativeCommandRecord{ID: 12, Damage: 340, Hit: 90, SelectionMode: 0, EffectMode: 1, MPCost: 80, TargetCode: 0}
	st := &State{W: 12, H: 12, Units: []*Unit{actor, far}, NativeCompositionEventBytes: make([]byte, 144), NativeCommandBook: book}

	if _, _, err := st.ExecuteNativeCommandDamage(actor, far, 12, map[int]int{5: 10}, 1, nil); err == nil || actor.MP != 90 || actor.Acted || far.HP != 200 {
		t.Fatalf("out-of-EffectMode-reach confirmed target must fail closed: actor=%#v far=%#v err=%v", actor, far, err)
	}
}
