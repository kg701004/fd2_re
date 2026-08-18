package battle

import "testing"

// zeroNativeCommandBook builds a shape-valid (37-record) NativeCommandBook
// with every field zeroed except ID. ScoreNativeAI1598A/ScoreNativeAI1567E
// require this exact shape before they'll even attempt to score anything;
// an all-zero-Damage book paired with an actor whose NativeCommandMask is
// also all-zero (no learned commands) is a realistic "basic enemy with no
// spellbook" fixture, not just a shape-satisfying stub.
func zeroNativeCommandBook() []NativeCommandRecord {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for i := range book {
		book[i] = NativeCommandRecord{ID: i}
	}
	return book
}

// TestNextAIPlanThreeScoreFullProvenancePhysicalWinsWithNoSpellbook exercises
// NextAIPlan with every precondition nativeAIThreeScorePlan gates on
// actually satisfied -- including a real, correctly-shaped NativeCommandBook,
// which native_ai_14237_apply_test.go's fixtures never set (so those tests
// were, before this wiring, silently exercising the legacy normalized
// fallback rather than the native composer -- see combat.go's NextAIPlan
// 2026-08-15 comment). The actor has no learned commands (zero
// NativeCommandMask) and no items, so spell/item scoring both find nothing
// and physical must still win, proving the three-pipeline gate doesn't
// regress the already-live-verified physical-only behavior once real
// production-shaped data (as cmd/fd2/main.go's bindNativeCommandBook
// provides) is present.
func TestNextAIPlanThreeScoreFullProvenancePhysicalWinsWithNoSpellbook(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 5, 5) // enemy
	actor.Camp = Enemy
	actor.NativeCommandMask = [5]byte{}
	actor.InventorySlots = []int{3, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}
	actor.NativeInventoryFlags = []int{0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80}
	actor.AP, actor.DP = 30, 5

	target := nativeAIMovementFallbackUnit(1, 6, 5) // ally, adjacent
	target.Camp = Own
	target.NativeCommandMask = [5]byte{}
	target.AP, target.DP = 5, 3
	target.HP, target.MaxHP = 100, 100

	st := nativeAIMovementFallbackFixtureState(10, 10, actor, target)
	st.NativeItemEffectRows = nativeAI14237FixtureItemRows(3, 2) // weapon range 2
	st.NativeCommandBook = zeroNativeCommandBook()

	plan := st.NextAIPlan()
	if plan == nil {
		t.Fatal("expected a plan")
	}
	if !plan.NativeSourced {
		t.Fatal("expected the plan to be native-sourced (three-score composer), not the legacy fallback")
	}
	if plan.Target != target {
		t.Fatalf("plan.Target = %v, want target", plan.Target)
	}
	if plan.SpellID != -1 {
		t.Fatalf("plan.SpellID = %d, want -1 (physical winner, not spell)", plan.SpellID)
	}
}

// TestNativeAIThreeScorePlanFailsClosedWithoutCommandBook confirms the
// fail-closed contract: a missing/wrong-shaped NativeCommandBook (the
// overwhelmingly common case in any State not built by cmd/fd2/main.go's
// bindNativeCommandBook) makes nativeAIThreeScorePlan report ok=false so
// NextAIPlan falls back to the legacy normalized planner entirely, matching
// nativeAI14237Plan's existing fail-closed behavior.
func TestNativeAIThreeScorePlanFailsClosedWithoutCommandBook(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 5, 5)
	actor.Camp = Enemy
	target := nativeAIMovementFallbackUnit(1, 6, 5)
	target.Camp = Own
	st := nativeAIMovementFallbackFixtureState(10, 10, actor, target)
	st.NativeItemEffectRows = nativeAI14237FixtureItemRows(3, 2)
	// st.NativeCommandBook intentionally left nil.

	plan, ok := st.nativeAIThreeScorePlan(actor)
	if ok {
		t.Fatalf("expected ok=false without a NativeCommandBook, got plan=%v", plan)
	}
	if plan != nil {
		t.Fatalf("expected nil plan alongside ok=false, got %v", plan)
	}
}
