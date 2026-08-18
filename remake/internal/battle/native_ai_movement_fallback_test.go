package battle

import "testing"

func uniformNativeMovementCostRows() [][]byte {
	rows := make([][]byte, NativeMovementCostRowCount)
	for i := range rows {
		row := make([]byte, NativeMovementCostRowSize)
		for j := range row {
			row[j] = 1
		}
		rows[i] = row
	}
	return rows
}

func nativeAIMovementFallbackFixtureState(w, h int, actor, opposite *Unit) *State {
	units := []*Unit{actor}
	if opposite != nil {
		units = append(units, opposite)
	}
	return &State{
		W: w, H: h, Units: units,
		NativeCompositionEventBytes: make([]byte, w*h),
		NativeTerrainMoveCodes:      make([]byte, w*h),
		NativeMovementCostRows:      uniformNativeMovementCostRows(),
	}
}

func nativeAIMovementFallbackUnit(camp byte, x, y int) *Unit {
	u := completeNativeAIScoringUnit()
	u.X, u.Y = x, y
	u.NativeMapPresentation.X, u.NativeMapPresentation.Y = byte(x), byte(y)
	u.NativeRecordByte6 = camp
	u.NativeRecordByte5 = 0       // active: bit0 clear
	u.NativeTransient = [6]byte{} // not poisoned/blocked
	u.ClassID = 0
	u.HasNativeRecordByte8 = true
	u.NativeRecordByte8 = 0 // avoid the row1/0x1c override
	u.MV = 20
	u.OnField, u.Group = true, 0
	u.HP, u.MaxHP = 50, 100
	// completeNativeAIScoringUnit's base fixture has byte34=0x81 (mode 1 in
	// the low nibble); pin it to mode 0 so ApplyNativeAIMovementFallback's
	// mode gate doesn't reject these fixtures.
	u.NativeRecordByte34, u.HasNativeRecordByte34 = 0x80, true
	// NativeAIScoringRecords writes record+0x42/+0x46 from these raw words,
	// not from u.MaxHP/u.MaxMP directly -- they must be kept in sync or the
	// raw record a test exercises silently uses stale max HP/MP.
	u.NativeRecordWord42, u.HasNativeRecordWord42 = 100, true
	u.NativeRecordWord46, u.HasNativeRecordWord46 = 0, true
	return u
}

func TestApplyNativeAIMovementFallbackMovesTowardReachableOpponent(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)  // enemy
	target := nativeAIMovementFallbackUnit(1, 5, 0) // ally, 5 cells away
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)

	result, ok := st.ApplyNativeAIMovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	if !result.Moved || result.Rested {
		t.Fatalf("expected a move, got %#v", result)
	}
	if actor.X == 0 && actor.Y == 0 {
		t.Fatal("actor did not move at all")
	}
	// Must not have moved onto the opponent's own cell.
	if actor.X == target.X && actor.Y == target.Y {
		t.Fatalf("actor moved onto the opposing unit's cell: %+v", actor)
	}
	// Must have moved strictly closer to the target.
	before := manhattan(0, 0, target.X, target.Y)
	after := manhattan(actor.X, actor.Y, target.X, target.Y)
	if after >= before {
		t.Fatalf("actor did not get closer: before=%d after=%d (actor now at %d,%d)", before, after, actor.X, actor.Y)
	}
}

func TestApplyNativeAIMovementFallbackRestsWhenNoOpponentExists(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.HP, actor.MaxHP = 50, 100
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)

	result, ok := st.ApplyNativeAIMovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	if !result.Rested || result.Moved {
		t.Fatalf("expected idle recovery, got %#v", result)
	}
	if actor.HP != 70 { // 50 + 100/5
		t.Fatalf("actor.HP = %d, want 70", actor.HP)
	}
	if actor.X != 0 || actor.Y != 0 {
		t.Fatal("resting unit must not move")
	}
}

func TestApplyNativeAIMovementFallbackFailsClosedWithoutRawProvenance(t *testing.T) {
	actor := &Unit{X: 0, Y: 0}
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)
	if _, ok := st.ApplyNativeAIMovementFallback(actor); ok {
		t.Fatal("unit lacking raw provenance must fail closed, not silently no-op")
	}
}

func TestApplyNativeAIMode1MovementFallbackMovesTowardReachableOpponent(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode1
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)

	result, ok := st.ApplyNativeAIMode1MovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	if !result.Moved || result.Rested {
		t.Fatalf("expected a move, got %#v", result)
	}
	if actor.X == target.X && actor.Y == target.Y {
		t.Fatalf("actor moved onto the opposing unit's cell: %+v", actor)
	}
}

// TestApplyNativeAIMode1MovementFallbackRestsWithoutTryingNearestOpposite is
// the behavioral difference from mode 0: place the opponent far enough away
// that budget-28 blocked-cell search can't reach it (so 0x14121 fails), but
// still trivially "nearest" since it's the only other unit. Mode 0 would
// fall back to 0x13E9C and move toward it anyway; mode 1 must not -- it has
// no such fallback and goes straight to idle recovery.
func TestApplyNativeAIMode1MovementFallbackRestsWithoutTryingNearestOpposite(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode1
	actor.HP, actor.MaxHP, actor.NativeRecordWord42 = 50, 100, 100
	target := nativeAIMovementFallbackUnit(1, 60, 0) // far beyond budget 28 at cost 1/cell
	st := nativeAIMovementFallbackFixtureState(70, 1, actor, target)

	result, ok := st.ApplyNativeAIMode1MovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	if !result.Rested || result.Moved {
		t.Fatalf("mode 1 must rest rather than fall back to nearest-opposite, got %#v (actor now at %d,%d)", result, actor.X, actor.Y)
	}
	if actor.X != 0 || actor.Y != 0 {
		t.Fatal("resting unit must not move")
	}
}

func TestApplyNativeAIMode1MovementFallbackFailsClosedForOtherModes(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	for _, mode := range []byte{0, 2, 3, 4, 5, 7, 8, 9, 10} {
		actor.NativeRecordByte34 = mode
		if _, ok := st.ApplyNativeAIMode1MovementFallback(actor); ok {
			t.Fatalf("mode %d must not run the mode-1 fallback chain", mode)
		}
	}
}

func TestApplyNativeAIMode2MovementFallbackAlwaysRestsNeverMoves(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode2
	actor.HP, actor.MaxHP, actor.NativeRecordWord42 = 50, 100, 100
	// Opponent placed right next to the actor -- if mode 2 had any
	// blocked-cell or nearest-opposite fallback, this is the easiest case
	// for it to fire. It must not: mode 2 always rests.
	target := nativeAIMovementFallbackUnit(1, 1, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)

	result, ok := st.ApplyNativeAIMode2MovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	if !result.Rested || result.Moved {
		t.Fatalf("mode 2 must always rest, never move, got %#v", result)
	}
	if actor.X != 0 || actor.Y != 0 {
		t.Fatal("mode 2 unit must not move")
	}
	if actor.HP != 70 {
		t.Fatalf("actor.HP = %d, want 70", actor.HP)
	}
}

func TestApplyNativeAIMode2MovementFallbackFailsClosedForOtherModes(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	for _, mode := range []byte{0, 1, 3, 4, 5, 7, 8, 9, 10} {
		actor.NativeRecordByte34 = mode
		if _, ok := st.ApplyNativeAIMode2MovementFallback(actor); ok {
			t.Fatalf("mode %d must not run the mode-2 fallback chain", mode)
		}
	}
}

func TestApplyNativeAIMode3MovementFallbackMovesTowardIdentityTarget(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode3
	actor.NativeRecordByte35, actor.HasNativeRecordByte35 = 77, true
	// Two candidates: a raw-opposite-group unit close by (would win mode 0's
	// 0x13E9C fallback) and the actual identity-77 target further away in a
	// different direction. Mode 3 must go to the identity target, not the
	// nearest opposite unit.
	nearbyOpposite := nativeAIMovementFallbackUnit(1, 1, 0)
	nearbyOpposite.NativeRecordByte8, nearbyOpposite.HasNativeRecordByte8 = 1, true
	identityTarget := nativeAIMovementFallbackUnit(1, 0, 5)
	identityTarget.NativeRecordByte8, identityTarget.HasNativeRecordByte8 = 77, true
	st := &State{
		W: 10, H: 10, Units: []*Unit{actor, nearbyOpposite, identityTarget},
		NativeCompositionEventBytes: make([]byte, 100),
		NativeTerrainMoveCodes:      make([]byte, 100),
		NativeMovementCostRows:      uniformNativeMovementCostRows(),
	}

	result, ok := st.ApplyNativeAIMode3MovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	if !result.Moved {
		t.Fatalf("expected a move, got %#v", result)
	}
	// Actor should end up strictly closer to (0,5) than to (1,0).
	toIdentity := manhattan(actor.X, actor.Y, 0, 5)
	toNearby := manhattan(actor.X, actor.Y, 1, 0)
	if toIdentity >= toNearby {
		t.Fatalf("actor at (%d,%d) did not move toward the identity target over the nearer opposite unit", actor.X, actor.Y)
	}
}

func TestApplyNativeAIMode3MovementFallbackFallsBackToFullMode0ChainWhenIdentityMissing(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode3
	actor.NativeRecordByte35, actor.HasNativeRecordByte35 = 99, true // no unit has this identity
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)

	result, ok := st.ApplyNativeAIMode3MovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	// With no identity match, mode 3 must run mode 0's full chain, which
	// (target reachable within budget 28) moves toward the nearest opposite
	// unit rather than resting.
	if !result.Moved || result.Rested {
		t.Fatalf("expected mode 0's fallback chain to fire, got %#v", result)
	}
}

func TestApplyNativeAIMode3MovementFallbackFailsClosedForOtherModesAndMissingIdentity(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	actor.NativeRecordByte34 = NativeAIDispatchMode3
	actor.HasNativeRecordByte35 = false
	if _, ok := st.ApplyNativeAIMode3MovementFallback(actor); ok {
		t.Fatal("missing record+0x35 provenance must fail closed")
	}
	actor.HasNativeRecordByte35 = true
	for _, mode := range []byte{0, 1, 2, 4, 5, 7, 8, 9, 10} {
		actor.NativeRecordByte34 = mode
		if _, ok := st.ApplyNativeAIMode3MovementFallback(actor); ok {
			t.Fatalf("mode %d must not run the mode-3 fallback chain", mode)
		}
	}
}

func TestApplyNativeAIMode8MovementFallbackDoesNothing(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode8
	actor.HP, actor.MaxHP, actor.NativeRecordWord42 = 50, 100, 100
	target := nativeAIMovementFallbackUnit(1, 1, 0) // adjacent, easiest case for any fallback to fire
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)

	result, ok := st.ApplyNativeAIMode8MovementFallback(actor)
	if !ok {
		t.Fatal("mode 8 must report ok=true (successfully reproduced: do nothing), not fall through to legacy")
	}
	if result.Moved || result.Rested {
		t.Fatalf("mode 8 must never move or rest, got %#v", result)
	}
	if actor.X != 0 || actor.Y != 0 || actor.HP != 50 {
		t.Fatalf("mode 8 unit must be completely untouched, got %+v", actor)
	}
}

func TestApplyNativeAIMode8MovementFallbackFailsClosedForOtherModes(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	for _, mode := range []byte{0, 1, 2, 3, 4, 5, 7, 9, 10} {
		actor.NativeRecordByte34 = mode
		if _, ok := (&State{}).ApplyNativeAIMode8MovementFallback(actor); ok {
			t.Fatalf("mode %d must not be treated as mode 8", mode)
		}
	}
}

func TestApplyNativeAIMode4MovementFallbackMovesTowardFixedCoordinate(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode4
	actor.NativeRecordByte35, actor.HasNativeRecordByte35 = 7, true // X
	actor.NativeRecordByte36, actor.HasNativeRecordByte36 = 0, true // Y
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)

	result, ok := st.ApplyNativeAIMode4MovementFallback(actor)
	if !ok || !result.Moved || result.Rested {
		t.Fatalf("expected a move toward (7,0), got result=%#v ok=%v", result, ok)
	}
	if actor.X != 7 || actor.Y != 0 {
		t.Fatalf("actor at (%d,%d), want exactly (7,0) within movement budget", actor.X, actor.Y)
	}
}

func TestApplyNativeAIMode7MovementFallbackDeactivatesOnExactArrival(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode7
	actor.NativeRecordByte35, actor.HasNativeRecordByte35 = 3, true
	actor.NativeRecordByte36, actor.HasNativeRecordByte36 = 0, true
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)

	result, ok := st.ApplyNativeAIMode7MovementFallback(actor)
	if !ok || !result.Moved {
		t.Fatalf("expected a move, got result=%#v ok=%v", result, ok)
	}
	if actor.X != 3 || actor.Y != 0 {
		t.Fatalf("actor at (%d,%d), want exactly (3,0)", actor.X, actor.Y)
	}
	if actor.NativeRecordByte5 != 1 {
		t.Fatalf("record+5 = %d, want 1 (deactivated) after landing exactly on target", actor.NativeRecordByte5)
	}
}

func TestApplyNativeAIMode9MovementFallbackDefersToLegacyWhenIdentityMissing(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode9
	actor.NativeRecordByte35, actor.HasNativeRecordByte35 = 99, true // no unit has this identity
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)

	if _, ok := st.ApplyNativeAIMode9MovementFallback(actor); ok {
		t.Fatal("mode 9 with no identity match must defer to legacy (ok=false), not guess a movement")
	}
}

func TestApplyNativeAIMode9MovementFallbackMovesTowardIdentityTarget(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode9
	actor.NativeRecordByte35, actor.HasNativeRecordByte35 = 42, true
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	target.NativeRecordByte8, target.HasNativeRecordByte8 = 42, true
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)

	result, ok := st.ApplyNativeAIMode9MovementFallback(actor)
	if !ok || !result.Moved {
		t.Fatalf("expected a move toward the identity target, got result=%#v ok=%v", result, ok)
	}
}

func TestApplyNativeAIMode10MovementFallbackMovesTowardFixedCoordinateWithoutDeactivating(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode10
	actor.NativeRecordByte35, actor.HasNativeRecordByte35 = 4, true
	actor.NativeRecordByte36, actor.HasNativeRecordByte36 = 0, true
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)

	result, ok := st.ApplyNativeAIMode10MovementFallback(actor)
	if !ok || !result.Moved {
		t.Fatalf("expected a move, got result=%#v ok=%v", result, ok)
	}
	if actor.X != 4 || actor.Y != 0 {
		t.Fatalf("actor at (%d,%d), want exactly (4,0)", actor.X, actor.Y)
	}
	if actor.NativeRecordByte5 != 0 {
		t.Fatalf("mode 10 must not deactivate on arrival (that's mode 7 only), record+5=%d", actor.NativeRecordByte5)
	}
}

func TestApplyNativeAIMode4Through10FailClosedForWrongModes(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte35, actor.HasNativeRecordByte35 = 7, true
	actor.NativeRecordByte36, actor.HasNativeRecordByte36 = 0, true
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)
	actor.NativeRecordByte34 = NativeAIDispatchMode0
	if _, ok := st.ApplyNativeAIMode4MovementFallback(actor); ok {
		t.Fatal("mode 4 executor must reject a mode-0 unit")
	}
	if _, ok := st.ApplyNativeAIMode5MovementFallback(actor); ok {
		t.Fatal("mode 5 executor must reject a mode-0 unit")
	}
	if _, ok := st.ApplyNativeAIMode7MovementFallback(actor); ok {
		t.Fatal("mode 7 executor must reject a mode-0 unit")
	}
	if _, ok := st.ApplyNativeAIMode9MovementFallback(actor); ok {
		t.Fatal("mode 9 executor must reject a mode-0 unit")
	}
	if _, ok := st.ApplyNativeAIMode10MovementFallback(actor); ok {
		t.Fatal("mode 10 executor must reject a mode-0 unit")
	}
}

func TestApplyNativeAIMode5MovementFallbackMovesTowardReachableOpponentWhenConsumed(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode5
	actor.NativeRecordByte3D, actor.HasNativeRecordByte3D = 2, true
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	st.NativeEventState[2] = 1 // event already consumed

	result, ok := st.ApplyNativeAIMode5MovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	if !result.Moved || result.Rested {
		t.Fatalf("expected a move (mode 1's own fallback body), got %#v", result)
	}
	if actor.X == target.X && actor.Y == target.Y {
		t.Fatalf("actor moved onto the opposing unit's cell: %+v", actor)
	}
}

func TestApplyNativeAIMode5MovementFallbackRestsWhenConsumedAndNoOpponent(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode5
	actor.NativeRecordByte3D, actor.HasNativeRecordByte3D = 9, true
	actor.HP, actor.MaxHP, actor.NativeRecordWord42 = 50, 100, 100
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)
	st.NativeEventState[9] = 1

	result, ok := st.ApplyNativeAIMode5MovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient")
	}
	if !result.Rested || result.Moved {
		t.Fatalf("expected idle recovery, got %#v", result)
	}
	if actor.HP != 70 {
		t.Fatalf("actor.HP = %d, want 70", actor.HP)
	}
}

// TestApplyNativeAIMode5MovementFallbackDefersWhenNotYetConsumed covers the
// case where the event hasn't fired AND State.Treasures has no cell for this
// event id (e.g. a map with no treasure data loaded at all): this must defer
// to the caller (ok=false) rather than guess a movement -- even though a
// reachable opposing unit exists, which would make a wrong guess easy to
// miss in a less careful test. See
// TestApplyNativeAIMode5MovementFallbackMovesTowardTreasureCellWhenNotYetConsumed
// for the case where a matching Treasure IS available.
func TestApplyNativeAIMode5MovementFallbackDefersWhenNotYetConsumed(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode5
	actor.NativeRecordByte3D, actor.HasNativeRecordByte3D = 2, true
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	// st.NativeEventState[2] left at zero: event not yet consumed.
	// st.Treasures left nil: no map data claims event id 2 as a treasure cell.

	if _, ok := st.ApplyNativeAIMode5MovementFallback(actor); ok {
		t.Fatal("event not yet consumed with no matching treasure data must defer to legacy (ok=false)")
	}
}

// TestApplyNativeAIMode5MovementFallbackMovesTowardTreasureCellWhenNotYetConsumed
// exercises the 0x15DF3 grid-scan reproduction: State.Treasures (already
// populated at Load time from tools/sync_native_treasures.py's per-cell
// treasure_slots/treasure_hidden output, see model.go's loadTreasures) is
// scanned for the cell whose Slot equals record+0x3D, and the actor moves
// toward it.
func TestApplyNativeAIMode5MovementFallbackMovesTowardTreasureCellWhenNotYetConsumed(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode5
	actor.NativeRecordByte3D, actor.HasNativeRecordByte3D = 2, true
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)
	// st.NativeEventState[2] left at zero: event not yet consumed.
	st.Treasures = map[Cell]Treasure{
		{X: 5, Y: 0}: {Slot: 2, Kind: "item", Value: 0x12},
	}

	result, ok := st.ApplyNativeAIMode5MovementFallback(actor)
	if !ok {
		t.Fatal("expected native data to be sufficient once State.Treasures has a matching slot")
	}
	if !result.Moved {
		t.Fatalf("expected a move toward the treasure cell, got %#v", result)
	}
	if actor.X == 0 && actor.Y == 0 {
		t.Fatal("actor did not move at all")
	}
	if d := manhattan(actor.X, actor.Y, 5, 0); d >= manhattan(0, 0, 5, 0) {
		t.Fatalf("actor did not move closer to the treasure cell: now at (%d,%d)", actor.X, actor.Y)
	}
}

func TestApplyNativeAIMode5MovementFallbackFailsClosedForMissingProvenance(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte34 = NativeAIDispatchMode5
	actor.HasNativeRecordByte3D = false
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, nil)
	if _, ok := st.ApplyNativeAIMode5MovementFallback(actor); ok {
		t.Fatal("missing record+0x3D provenance must fail closed")
	}

	actor.NativeRecordByte3D, actor.HasNativeRecordByte3D = 0x20, true // out of NativeEventState's 0x20 bounds
	if _, ok := st.ApplyNativeAIMode5MovementFallback(actor); ok {
		t.Fatal("out-of-bounds record+0x3D must fail closed")
	}
}

func TestApplyNativeAIMode5MovementFallbackFailsClosedForOtherModes(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	actor.NativeRecordByte3D, actor.HasNativeRecordByte3D = 2, true
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	st.NativeEventState[2] = 1
	for _, mode := range []byte{0, 1, 2, 3, 4, 7, 8, 9, 10} {
		actor.NativeRecordByte34 = mode
		if _, ok := st.ApplyNativeAIMode5MovementFallback(actor); ok {
			t.Fatalf("mode %d must not run the mode-5 fallback chain", mode)
		}
	}
}

func TestApplyNativeAIMovementFallbackFailsClosedForNonMode0Units(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	target := nativeAIMovementFallbackUnit(1, 5, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	for mode := byte(1); mode <= 10; mode++ {
		actor.NativeRecordByte34 = mode // low nibble only; matches doc11's mode field
		actor.X, actor.Y = 0, 0
		if _, ok := st.ApplyNativeAIMovementFallback(actor); ok {
			t.Fatalf("mode %d must not run the mode-0 fallback chain", mode)
		}
	}
}
