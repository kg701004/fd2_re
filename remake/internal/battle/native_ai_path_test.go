package battle

import (
	"reflect"
	"testing"
)

func TestSelectNativeMovementDestinationUsesDistanceThenAxisBalance(t *testing.T) {
	candidates := []Cell{
		{X: 3, Y: 0}, // distance 3, imbalance 3
		{X: 2, Y: 1}, // distance 3, imbalance 1
		{X: 1, Y: 2}, // exact metric tie: later must not replace
	}
	got, ok := SelectNativeMovementDestination(candidates, Cell{})
	if !ok || got != candidates[1] {
		t.Fatalf("destination=%v ok=%v", got, ok)
	}
}

func TestSelectNativeMovementDestinationPreservesNativeFFSentinel(t *testing.T) {
	intended := Cell{}
	got, ok := SelectNativeMovementDestination([]Cell{{X: 255, Y: 0}}, intended)
	if ok || got != intended {
		t.Fatalf("destination=%v ok=%v", got, ok)
	}
}

func TestSelectNativeNearestOppositeCoordinateKeepsFirstTie(t *testing.T) {
	records := make([]byte, 4*nativeRecordSize)
	records[0], records[1], records[6] = 5, 5, 0
	records[nativeRecordSize+0], records[nativeRecordSize+1], records[nativeRecordSize+6] = 4, 3, 1
	records[2*nativeRecordSize+0], records[2*nativeRecordSize+1], records[2*nativeRecordSize+6] = 7, 4, 2
	records[3*nativeRecordSize+0], records[3*nativeRecordSize+1], records[3*nativeRecordSize+6] = 5, 4, 0

	got, ok, err := SelectNativeNearestOppositeCoordinate(records, 4, 0, 0)
	if err != nil || !ok || got != (Cell{X: 4, Y: 3}) {
		t.Fatalf("coordinate=%v ok=%v err=%v", got, ok, err)
	}
}

func TestNativePathDirectionsMatchesNativeOrderAndTerrainCosts(t *testing.T) {
	costRow := make([]byte, NativeMovementCostRowSize)
	costRow[0], costRow[1] = 1, 2
	got, ok, err := NativePathDirections(
		3, 3,
		Cell{X: 0, Y: 1}, Cell{X: 2, Y: 1},
		4, 0,
		make([]byte, 9),
		[]byte{0, 0, 0, 0, 1, 0, 0, 0, 0},
		costRow,
	)
	if err != nil || !ok {
		t.Fatalf("path=%v ok=%v err=%v", got, ok, err)
	}
	// Direct right/right costs 3 and is explored before the detours.
	if !reflect.DeepEqual(got, []byte{NativePathRight, NativePathRight}) {
		t.Fatalf("path=%v", got)
	}
}

func TestNativePathDirectionsHonoursBlockedAndTerminalFlags(t *testing.T) {
	costRow := make([]byte, NativeMovementCostRowSize)
	costRow[0] = 1
	flags := make([]byte, 5)
	flags[2] = NativeCommandGridBlocked
	if path, ok, err := NativePathDirections(
		5, 1, Cell{}, Cell{X: 4}, 5, 0,
		flags, make([]byte, 5), costRow,
	); err != nil || ok || path != nil {
		t.Fatalf("blocked path=%v ok=%v err=%v", path, ok, err)
	}

	flags[2] = NativeCommandGridZeroBudget
	if path, ok, err := NativePathDirections(
		5, 1, Cell{}, Cell{X: 4}, 5, 0,
		flags, make([]byte, 5), costRow,
	); err != nil || ok || path != nil {
		t.Fatalf("terminal path=%v ok=%v err=%v", path, ok, err)
	}
}

func TestNativePathDirectionsReturnsEmptyPathAtDestination(t *testing.T) {
	costRow := make([]byte, NativeMovementCostRowSize)
	costRow[0] = 1
	path, ok, err := NativePathDirections(
		1, 1, Cell{}, Cell{}, 0, 0,
		[]byte{0}, []byte{0}, costRow,
	)
	if err != nil || !ok || len(path) != 0 {
		t.Fatalf("path=%v ok=%v err=%v", path, ok, err)
	}
}

func TestNativePathBlockedCoordinateKeepsLastDFSBlockedCell(t *testing.T) {
	costRow := make([]byte, NativeMovementCostRowSize)
	costRow[0] = 1
	flags := make([]byte, 5)
	flags[1] = NativeCommandGridBlocked
	flags[4] = NativeCommandGridBlocked
	got, ok, err := NativePathBlockedCoordinate(
		5, 1, Cell{}, 5,
		flags, make([]byte, 5), costRow,
	)
	if err != nil || !ok || got != (Cell{X: 4}) {
		t.Fatalf("blocked coordinate=%v ok=%v err=%v", got, ok, err)
	}
}
