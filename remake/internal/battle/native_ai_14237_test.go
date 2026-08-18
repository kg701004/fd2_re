package battle

import (
	"encoding/binary"
	"testing"
)

func nativeAI14237PutWord(record []byte, offset int, value uint16) {
	binary.LittleEndian.PutUint16(record[offset:offset+2], value)
}

func nativeAI14237FixtureItemRows(itemID byte, rangeTiles byte) []byte {
	rows := make([]byte, (int(itemID)+1)*NativeItemEffectRowSize)
	rows[int(itemID)*NativeItemEffectRowSize+0x0c] = rangeTiles
	return rows
}

// nativeAI14237Fixture builds a 3x3 grid, uniform movement cost 1, an actor
// at (1,1) with a range-2 weapon equipped and no terrain-percent gate
// applying (ClassID/race left zero -- the adjustment block is simply
// skipped, exercising the "gate false" path), and one opposing target at
// (2,1), one tile away.
func nativeAI14237Fixture(actorAP, actorDP, targetAP, targetDP, targetHP uint16) ([]byte, []byte) {
	records := make([]byte, 2*nativeRecordSize)
	actor := records[0:nativeRecordSize]
	actor[0], actor[1] = 1, 1 // position
	actor[0x3b] = 3           // remaining movement budget
	actor[nativeInventoryOffset] = 0x40
	actor[nativeInventoryOffset+1] = 0x05 // item id 5 equipped
	nativeAI14237PutWord(actor, 0x48, actorAP)
	nativeAI14237PutWord(actor, 0x4a, actorDP)

	target := records[nativeRecordSize : 2*nativeRecordSize]
	target[0], target[1] = 2, 1
	target[6] = 1 // opposing group vs. actor's selector 0
	target[8] = 1 // != 0: disable the raw-byte8 3/2 multiplier for this base fixture
	nativeAI14237PutWord(target, 0x48, targetAP)
	nativeAI14237PutWord(target, 0x4a, targetDP)
	nativeAI14237PutWord(target, 0x40, targetHP)

	itemRows := nativeAI14237FixtureItemRows(5, 2)
	return records, itemRows
}

func TestScoreNativeAI14237PicksReachableTargetWithinWeaponRange(t *testing.T) {
	records, itemRows := nativeAI14237Fixture(20, 5, 10, 3, 50)
	costRow := uniformNativeMovementCostRows()[0]
	terrainCodes := make([]byte, 9)

	result, err := ScoreNativeAI14237(3, 3, records, 2, 0, 0, itemRows, make([]byte, 9), terrainCodes, costRow)
	if err != nil {
		t.Fatal(err)
	}
	if !result.HasWinner {
		t.Fatal("expected a winning candidate")
	}
	if result.TargetIndex != 1 {
		t.Fatalf("target index = %d, want 1", result.TargetIndex)
	}
	// score = actorAP(20) - targetDP(3) = 17 > targetHP? no (17<50) so priority stays 8, no 1DEBE bonus expected
	// (actor at its own start cell (1,1) is not adjacent to itself).
	if result.Priority != 8 {
		t.Fatalf("priority = %d, want 8", result.Priority)
	}
	if result.Score != 17 {
		t.Fatalf("score = %d, want 17 (20-3)", result.Score)
	}
}

func TestScoreNativeAI14237NoWinnerWithoutEquippedWeapon(t *testing.T) {
	records, itemRows := nativeAI14237Fixture(20, 5, 10, 3, 50)
	records[nativeInventoryOffset] = 0 // unequip the weapon
	costRow := uniformNativeMovementCostRows()[0]
	terrainCodes := make([]byte, 9)

	result, err := ScoreNativeAI14237(3, 3, records, 2, 0, 0, itemRows, make([]byte, 9), terrainCodes, costRow)
	if err != nil {
		t.Fatal(err)
	}
	if result.HasWinner {
		t.Fatal("expected no winner when no weapon is equipped, matching 0x14237's own early return")
	}
}

// TestScoreNativeAI14237AppliesByte8MultiplierAnd1DEBEBonus exercises the
// full end-of-formula path through the composer (not just the already-unit-
// tested ScoreNativePhysicalAttackCandidate primitive): a destination cell
// exactly one step from the actor's own real position (so
// NativeAI1DEBEAdjacencyGate fires) that is also within weapon range of the
// target, combined with the target's raw byte+8==0 (default) triggering the
// 3/2 multiplier -- both must be applied together, in the order the
// disassembly showed (1DEBE add, then the 3/2 multiply).
func TestScoreNativeAI14237AppliesByte8MultiplierAnd1DEBEBonus(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	actor := records[0:nativeRecordSize]
	actor[0], actor[1] = 2, 2
	actor[0x3b] = 3
	actor[nativeInventoryOffset] = 0x40
	actor[nativeInventoryOffset+1] = 0x05
	nativeAI14237PutWord(actor, 0x48, 20) // AP
	nativeAI14237PutWord(actor, 0x4a, 6)  // DP -- used by the 1DEBE bonus term

	target := records[nativeRecordSize : 2*nativeRecordSize]
	target[0], target[1] = 2, 0
	target[6] = 1
	// target[8] left at 0: triggers the 3/2 multiplier.
	nativeAI14237PutWord(target, 0x48, 4) // AP -- used by the 1DEBE bonus term
	nativeAI14237PutWord(target, 0x4a, 3) // DP
	nativeAI14237PutWord(target, 0x40, 100)

	// Weapon row +0x0b left at 0 (<=1, satisfies 1DEBE's melee gate); range 3
	// so the destination (2,1), one tile from target (2,0), qualifies.
	itemRows := nativeAI14237FixtureItemRows(5, 3)
	costRow := uniformNativeMovementCostRows()[0]
	terrainCodes := make([]byte, 25)

	result, err := ScoreNativeAI14237(5, 5, records, 2, 0, 0, itemRows, make([]byte, 25), terrainCodes, costRow)
	if err != nil {
		t.Fatal(err)
	}
	if !result.HasWinner {
		t.Fatal("expected a winning candidate")
	}
	// base = actorAP(20) - targetDP(3) = 17; +1DEBE bonus actorDP(6)-targetAP(4) = 2 -> 19;
	// byte8==0 multiplier: 19*3/2 = 28 (truncated toward zero).
	if result.Score != 28 {
		t.Fatalf("score = %d, want 28 (base 17 +1DEBE bonus 2 = 19, ×3/2 = 28)", result.Score)
	}
}

func TestScoreNativeAI14237RejectsLowValueCandidate(t *testing.T) {
	// actorAP-targetDP <= 2 must be rejected entirely (doc11 step 5).
	records, itemRows := nativeAI14237Fixture(5, 5, 10, 4, 50)
	costRow := uniformNativeMovementCostRows()[0]
	terrainCodes := make([]byte, 9)

	result, err := ScoreNativeAI14237(3, 3, records, 2, 0, 0, itemRows, make([]byte, 9), terrainCodes, costRow)
	if err != nil {
		t.Fatal(err)
	}
	if result.HasWinner {
		t.Fatalf("expected no winner (score %d-%d=1 <= 2), got %+v", 5, 4, result)
	}
}
