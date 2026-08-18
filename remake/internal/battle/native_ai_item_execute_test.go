package battle

import "encoding/binary"

import "testing"

// itemFixtureRows builds a shape-valid itemRows table with a single
// HP-restore row (native item type 5, ConsumesSource=true) at itemID,
// matching NativeItemHPRestoreRouteForType's case 5. SelectionMode/
// EffectMode/TargetCode mirror TestNativeItemEffectTargetsUsesConfirmedSecondStageOrigin's
// already-proven-working parameters (1/1/0) -- this test isn't about
// target-selection geometry, just proving ApplyNativeAIItemCommand's
// RouteForType cascade + records/sync bookkeeping actually runs end to end.
func itemFixtureRows(itemID int, amount uint16) []byte {
	rows := make([]byte, (itemID+1)*NativeItemEffectRowSize)
	row := rows[itemID*NativeItemEffectRowSize:]
	row[0x0d] = 5 // HP restore, consumes source
	binary.LittleEndian.PutUint16(row[0x0e:0x10], amount)
	row[0x10] = 1 // SelectionMode
	row[0x12] = 1 // EffectMode
	row[0x15] = 1 // TargetCode: NativeCommandTargetMatches(1, camp) matches non-Enemy (Own/Ally)
	return rows
}

func TestApplyNativeAIItemCommandRestoresHPAndConsumesSlot(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	// Override the shared fixture's raw camp byte to 2 (Own, a no-op for
	// nativeCommandTargetCodeForSelector): this test is about the
	// RouteForType cascade, not team-relative target-code reflection, and
	// the fixture's target below never set its Go Camp field to a value
	// consistent with the "camp=0 (native Enemy)" test-helper convention --
	// only the raw-selector no-op keeps this test's original working
	// target-matching (TargetCode 1 matches non-Enemy) intact.
	actor.NativeRecordByte6 = 2
	actor.InventorySlots = []int{7, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}
	actor.NativeInventoryFlags = []int{0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80}

	target := nativeAIMovementFallbackUnit(1, 1, 0)
	target.HP, target.MaxHP = 40, 100
	target.NativeRecordWord42, target.HasNativeRecordWord42 = 100, true

	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	itemID := 7
	rows := itemFixtureRows(itemID, 30)

	applied, nextRNG, err := st.ApplyNativeAIItemCommand(actor, target, itemID, 0, rows, 0x1234)
	if err != nil {
		t.Fatal(err)
	}
	if !applied {
		t.Fatal("expected the HP restore to apply")
	}
	if target.HP <= 40 {
		t.Fatalf("target.HP = %d, want restored above 40", target.HP)
	}
	if actor.InventorySlots[0] != 0xff || actor.NativeInventoryFlags[0]&0x80 == 0 {
		t.Fatalf("expected source slot 0 consumed, got slots=%v flags=%v", actor.InventorySlots, actor.NativeInventoryFlags)
	}
	_ = nextRNG
}

func TestApplyNativeAIItemCommandFailsClosedOnBadRow(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	target := nativeAIMovementFallbackUnit(1, 1, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)

	applied, _, err := st.ApplyNativeAIItemCommand(actor, target, 3, 0, nil, 0)
	if err == nil {
		t.Fatal("expected an error for an unavailable item row")
	}
	if applied {
		t.Fatal("expected applied=false alongside the error")
	}
}

func TestApplyNativeAIItemCommandDefersOnRelocationType(t *testing.T) {
	actor := nativeAIMovementFallbackUnit(0, 0, 0)
	target := nativeAIMovementFallbackUnit(1, 1, 0)
	st := nativeAIMovementFallbackFixtureState(10, 1, actor, target)
	itemID := 2
	rows := itemFixtureRows(itemID, 0)
	rows[itemID*NativeItemEffectRowSize+0x0d] = 23 // relocation type

	applied, _, err := st.ApplyNativeAIItemCommand(actor, target, itemID, 0, rows, 0)
	if err != nil {
		t.Fatalf("relocation type should defer cleanly, not error: %v", err)
	}
	if applied {
		t.Fatal("expected applied=false for the unsupported relocation type")
	}
}
