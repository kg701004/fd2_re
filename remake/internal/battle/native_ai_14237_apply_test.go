package battle

import "testing"

// TestNextAIPlanUsesNativeAI14237WhenFullProvenanceAvailable exercises the
// real production entry point (combat.go's NextAIPlan -- the function
// main.go's aiStep() actually calls once per enemy unit's turn; aiActUnit is
// dead code, not a production path). Confirms the native composer's chosen
// destination+target reach NextAIPlan's returned *AIPlan* unmodified, using
// the same complete-provenance fixture style as
// native_ai_movement_fallback_test.go.
//
// The grid here is uniform terrain, so many reachable destinations tie in
// score; ScoreNativeAI14237's disassembly-confirmed tie-break is "earliest
// row-major (y then x) enumeration", not "nearest to the actor's current
// cell" -- so this deliberately does NOT assert Path is empty even though
// the actor starts adjacent to target. It only asserts the final path cell
// (or the actor's own cell if no walk) is within the weapon's range of
// target, which is what the composer guarantees.
func TestNextAIPlanUsesNativeAI14237WhenFullProvenanceAvailable(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 5, 5) // enemy
	actor.Camp = Enemy                             // NextAIPlan's eligibility loop keys off the legacy Camp field
	actor.InventorySlots = []int{3, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}
	actor.NativeInventoryFlags = []int{0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80}
	actor.AP, actor.DP = 30, 5

	target := nativeAIMovementFallbackUnit(1, 6, 5) // ally, adjacent (own group's opposing camp)
	target.Camp = Own
	target.AP, target.DP = 5, 3
	target.HP, target.MaxHP = 100, 100

	st := nativeAIMovementFallbackFixtureState(10, 10, actor, target)
	st.NativeItemEffectRows = nativeAI14237FixtureItemRows(3, 2) // weapon range 2

	plan := st.NextAIPlan()
	if plan == nil {
		t.Fatal("expected a plan")
	}
	if plan.U != actor {
		t.Fatalf("plan.U = %v, want actor", plan.U)
	}
	if plan.Target != target {
		t.Fatalf("plan.Target = %v, want target (native composer should have picked it)", plan.Target)
	}
	destX, destY := actor.X, actor.Y
	if n := len(plan.Path); n > 0 {
		destX, destY = plan.Path[n-1].X, plan.Path[n-1].Y
	}
	if d := manhattan(destX, destY, target.X, target.Y); d > 2 {
		t.Fatalf("planned destination (%d,%d) is %d cells from target, outside weapon range 2", destX, destY, d)
	}
}

// TestNextAIPlanFallsBackWithoutNativeItemEffectRows confirms the fail-closed
// contract: when native item-row data isn't bound to the State (the
// overwhelmingly common case today -- see bindNativeAIItemEffectRows in
// cmd/fd2/main.go), NextAIPlan falls through to its pre-existing normalized
// aiTargets/estDamage planning entirely, unchanged.
func TestNextAIPlanFallsBackWithoutNativeItemEffectRows(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 5, 5)
	actor.Camp = Enemy
	actor.AP, actor.DP = 30, 5
	target := nativeAIMovementFallbackUnit(1, 6, 5)
	target.Camp = Own
	target.AP, target.DP = 5, 3
	target.HP, target.MaxHP = 100, 100
	st := nativeAIMovementFallbackFixtureState(10, 10, actor, target)
	// st.NativeItemEffectRows intentionally left nil.

	plan := st.NextAIPlan()
	if plan == nil {
		t.Fatal("expected a plan")
	}
	if plan.Target != target {
		t.Fatalf("expected the legacy normalized planner to still find the adjacent target, got %v", plan.Target)
	}
}
