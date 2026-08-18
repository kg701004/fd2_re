package battle

import "testing"

func native1DEBEFixtureRecords(count int) []byte {
	return make([]byte, count*nativeRecordSize)
}

func TestNativeAI1DEBEAdjacencyGateTrueWhenAdjacentActiveAndLowRange(t *testing.T) {
	records := native1DEBEFixtureRecords(1)
	record := records[0:]
	record[0], record[1] = 5, 5 // actor at (5,5)
	record[nativeInventoryOffset] = 0x40  // slot0 equipped
	record[nativeInventoryOffset+1] = 0x02 // item id 2, <0x80
	itemRows := make([]byte, 3*NativeItemEffectRowSize)
	itemRows[2*NativeItemEffectRowSize+0x0b] = 1 // item 2's row +0x0b == 1

	got, err := NativeAI1DEBEAdjacencyGate(records, itemRows, 1, 0, 6, 5)
	if err != nil {
		t.Fatal(err)
	}
	if !got {
		t.Fatal("expected the gate to hold for an adjacent, active, low-range actor")
	}
}

func TestNativeAI1DEBEAdjacencyGateFalseWhenNotAdjacent(t *testing.T) {
	records := native1DEBEFixtureRecords(1)
	record := records[0:]
	record[0], record[1] = 5, 5
	record[nativeInventoryOffset] = 0x40
	record[nativeInventoryOffset+1] = 0x02
	itemRows := make([]byte, 3*NativeItemEffectRowSize)
	itemRows[2*NativeItemEffectRowSize+0x0b] = 1

	for _, cell := range []struct{ x, y int }{{5, 5}, {7, 5}, {5, 7}, {6, 6}} {
		got, err := NativeAI1DEBEAdjacencyGate(records, itemRows, 1, 0, cell.x, cell.y)
		if err != nil {
			t.Fatal(err)
		}
		if got {
			t.Fatalf("(%d,%d) is not Manhattan-adjacent to (5,5), gate must be false", cell.x, cell.y)
		}
	}
}

func TestNativeAI1DEBEAdjacencyGateFalseWhenInactive(t *testing.T) {
	records := native1DEBEFixtureRecords(1)
	record := records[0:]
	record[0], record[1] = 5, 5
	record[5] = 1 // inactive: bit0 set
	record[nativeInventoryOffset] = 0x40
	record[nativeInventoryOffset+1] = 0x02
	itemRows := make([]byte, 3*NativeItemEffectRowSize)
	itemRows[2*NativeItemEffectRowSize+0x0b] = 1

	got, err := NativeAI1DEBEAdjacencyGate(records, itemRows, 1, 0, 6, 5)
	if err != nil {
		t.Fatal(err)
	}
	if got {
		t.Fatal("inactive actor must fail the gate")
	}
}

func TestNativeAI1DEBEAdjacencyGateFalseWhenNoWeaponEquipped(t *testing.T) {
	records := native1DEBEFixtureRecords(1)
	record := records[0:]
	record[0], record[1] = 5, 5
	// No inventory cell has flag bit 0x40 set -- no equipped weapon.
	itemRows := make([]byte, 3*NativeItemEffectRowSize)

	got, err := NativeAI1DEBEAdjacencyGate(records, itemRows, 1, 0, 6, 5)
	if err != nil {
		t.Fatal(err)
	}
	if got {
		t.Fatal("no equipped weapon must fail the gate, not be silently skipped")
	}
}

func TestNativeAI1DEBEAdjacencyGateFalseWhenRowExceedsThreshold(t *testing.T) {
	records := native1DEBEFixtureRecords(1)
	record := records[0:]
	record[0], record[1] = 5, 5
	record[nativeInventoryOffset] = 0x40
	record[nativeInventoryOffset+1] = 0x02
	itemRows := make([]byte, 3*NativeItemEffectRowSize)
	itemRows[2*NativeItemEffectRowSize+0x0b] = 2 // row +0x0b > 1

	got, err := NativeAI1DEBEAdjacencyGate(records, itemRows, 1, 0, 6, 5)
	if err != nil {
		t.Fatal(err)
	}
	if got {
		t.Fatal("row +0x0b > 1 must fail the gate")
	}
}

func TestNativeAI1DEBEAdjacencyGateFailsClosedOnMalformedInputs(t *testing.T) {
	itemRows := make([]byte, NativeItemEffectRowSize)
	if _, err := NativeAI1DEBEAdjacencyGate(nil, itemRows, 1, 0, 0, 0); err == nil {
		t.Fatal("empty records must fail closed")
	}
	records := native1DEBEFixtureRecords(1)
	if _, err := NativeAI1DEBEAdjacencyGate(records, nil, 1, 0, 0, 0); err == nil {
		t.Fatal("empty item rows must fail closed")
	}
	if _, err := NativeAI1DEBEAdjacencyGate(records, itemRows, 1, 5, 0, 0); err == nil {
		t.Fatal("out-of-range actor index must fail closed")
	}
}
