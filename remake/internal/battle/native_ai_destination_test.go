package battle

import (
	"reflect"
	"testing"
)

func TestNativeAIPhysicalDestinationsUsesNativeCostsAndRowMajorOrder(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0], records[1], records[6] = 1, 1, 0
	costRow := make([]byte, NativeMovementCostRowSize)
	costRow[1], costRow[2] = 1, 2
	codes := []byte{
		1, 1, 1,
		2, 1, 1,
		1, 1, 1,
	}
	got, err := NativeAIPhysicalDestinations(
		3, 3, records, 1, 0, 0, 2,
		make([]byte, 9), codes, costRow,
	)
	if err != nil {
		t.Fatal(err)
	}
	want := []Cell{
		{X: 0, Y: 0}, {X: 1, Y: 0}, {X: 2, Y: 0},
		{X: 0, Y: 1}, {X: 1, Y: 1}, {X: 2, Y: 1},
		{X: 0, Y: 2}, {X: 1, Y: 2}, {X: 2, Y: 2},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("destinations=%v want=%v", got, want)
	}
}

func TestNativeAIPhysicalDestinationsAppliesOccupancyBeforeAndAfterSearch(t *testing.T) {
	records := make([]byte, 3*nativeRecordSize)
	actor := records[:nativeRecordSize]
	actor[0], actor[1], actor[6] = 0, 1, 0
	sameGroup := records[nativeRecordSize : 2*nativeRecordSize]
	sameGroup[0], sameGroup[1], sameGroup[6] = 1, 1, 0
	oppositeGroup := records[2*nativeRecordSize:]
	oppositeGroup[0], oppositeGroup[1], oppositeGroup[6] = 3, 1, 1

	costRow := make([]byte, NativeMovementCostRowSize)
	costRow[0] = 1
	got, err := NativeAIPhysicalDestinations(
		5, 3, records, 3, 0, 0, 5,
		make([]byte, 15), make([]byte, 15), costRow,
	)
	if err != nil {
		t.Fatal(err)
	}
	for _, forbidden := range []Cell{{X: 1, Y: 1}, {X: 3, Y: 1}, {X: 4, Y: 1}} {
		for _, cell := range got {
			if cell == forbidden {
				t.Fatalf("occupied/blocked destination %v leaked into %v", forbidden, got)
			}
		}
	}
	// The opposite group's adjacent cell is enterable but terminal.
	foundTerminal := false
	for _, cell := range got {
		if cell == (Cell{X: 2, Y: 1}) {
			foundTerminal = true
		}
	}
	if !foundTerminal {
		t.Fatalf("terminal adjacent cell missing from %v", got)
	}
}

func TestNativeAIPhysicalDestinationsRejectsIncompleteRawInputs(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0], records[1] = 0, 0
	costRow := make([]byte, NativeMovementCostRowSize)
	_, err := NativeAIPhysicalDestinations(
		1, 1, records, 1, 0, 0, 1,
		[]byte{0}, []byte{NativeMovementCostRowSize}, costRow,
	)
	if err == nil {
		t.Fatal("out-of-range native terrain code accepted")
	}
}
