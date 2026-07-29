package battle

import (
	"reflect"
	"testing"
)

func nativeAIScoredCandidateFixture() ([]byte, []byte, []byte) {
	records := make([]byte, 4*nativeRecordSize)
	records[0], records[1], records[6] = 1, 1, 0
	records[nativeRecordSize], records[nativeRecordSize+1], records[nativeRecordSize+6] = 0, 1, 2
	records[2*nativeRecordSize], records[2*nativeRecordSize+1], records[2*nativeRecordSize+6] = 2, 1, 1
	records[3*nativeRecordSize], records[3*nativeRecordSize+1], records[3*nativeRecordSize+6] = 1, 0, 2
	flags := make([]byte, 9)
	terrain := make([]byte, 9)
	return records, flags, terrain
}

func TestNativeAIScoredCommandCandidateGroupsPreservesGeometryAndRawOrder(t *testing.T) {
	records, flags, terrain := nativeAIScoredCandidateFixture()
	cost := make([]byte, NativeMovementCostRowSize)
	for index := range cost {
		cost[index] = 1
	}
	command := NativeCommandRecord{
		SelectionMode: 1,
		EffectMode:    1,
		TargetCode:    0,
	}
	groups, err := NativeAIScoredCommandCandidateGroups(
		3, 3, records, 4, 0, 0, command, flags, terrain, cost,
	)
	if err != nil {
		t.Fatal(err)
	}
	want := []NativeAIScoredCommandCandidateGroup{
		{Destination: Cell{X: 1, Y: 0}, TargetIndices: []byte{3}},
		{Destination: Cell{X: 0, Y: 1}, TargetIndices: []byte{1}},
		{Destination: Cell{X: 1, Y: 1}, TargetIndices: []byte{1, 2, 3}},
		{Destination: Cell{X: 2, Y: 1}, TargetIndices: []byte{2}},
	}
	if !reflect.DeepEqual(groups, want) {
		t.Fatalf("groups=%#v want=%#v", groups, want)
	}
}

func TestNativeAIScoredCommandCandidateGroupsSelectorOneUsesCommandTargetCode(t *testing.T) {
	records, flags, terrain := nativeAIScoredCandidateFixture()
	cost := make([]byte, NativeMovementCostRowSize)
	for index := range cost {
		cost[index] = 1
	}
	command := NativeCommandRecord{SelectionMode: 0, EffectMode: 1, TargetCode: 0}
	groups, err := NativeAIScoredCommandCandidateGroups(
		3, 3, records, 4, 0, 1, command, flags, terrain, cost,
	)
	if err != nil {
		t.Fatal(err)
	}
	if len(groups) != 1 || !reflect.DeepEqual(groups[0].TargetIndices, []byte{0}) {
		t.Fatalf("selector-one target groups=%#v", groups)
	}
}

func TestNativeAIScoredCommandCandidateGroupsDoesNotInventPhysicalOccupancyFlags(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[0], records[1], records[6] = 0, 0, 0
	records[nativeRecordSize], records[nativeRecordSize+1], records[nativeRecordSize+6] = 1, 0, 2
	flags := make([]byte, 2)
	terrain := make([]byte, 2)
	cost := make([]byte, NativeMovementCostRowSize)
	for index := range cost {
		cost[index] = 1
	}
	command := NativeCommandRecord{SelectionMode: 1, EffectMode: 0, TargetCode: 0}
	groups, err := NativeAIScoredCommandCandidateGroups(
		2, 1, records, 2, 0, 0, command, flags, terrain, cost,
	)
	if err != nil {
		t.Fatal(err)
	}
	if len(groups) != 1 || groups[0].Destination != (Cell{X: 1, Y: 0}) {
		t.Fatalf("roster-derived blocker was invented: %#v", groups)
	}
}

func TestNativeAIScoredCommandCandidateGroupsFailsClosedOnMalformedInputs(t *testing.T) {
	records, flags, terrain := nativeAIScoredCandidateFixture()
	cost := make([]byte, NativeMovementCostRowSize)
	command := NativeCommandRecord{SelectionMode: 1, EffectMode: 1}
	if _, err := NativeAIScoredCommandCandidateGroups(
		3, 3, records[:len(records)-1], 4, 0, 0, command, flags, terrain, cost,
	); err == nil {
		t.Fatal("short record buffer accepted")
	}
	if _, err := NativeAIScoredCommandCandidateGroups(
		3, 3, records, 4, 0, 2, command, flags, terrain, cost,
	); err == nil {
		t.Fatal("unknown selector accepted")
	}
}

func TestMap0AssetsBuildNativeAIScoredCommandCandidateGroups(t *testing.T) {
	st, err := Load("../../assets/maps/map0/map0_units.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, unit := range st.Units {
		if err := unit.MaterializeNativeMapPresentation(); err != nil {
			t.Fatal(err)
		}
	}
	records, err := NativeAIScoringRecords(st.Units)
	if err != nil {
		t.Fatal(err)
	}
	book, err := LoadNativeCommandRecords("../../assets/spells.json")
	if err != nil {
		t.Fatal(err)
	}
	rows, err := LoadNativeMovementCostRows("../../assets/data/native_movement_cost_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	actor, target := -1, -1
	for index, unit := range st.Units {
		if actor < 0 && unit.NativeRecordByte8 == 103 &&
			unit.HasNativeRecordByte8 && !unit.HasNativeIdentity {
			actor = index
		}
		if target < 0 && unit.NativeRecordByte6 == 1 && unit.HasNativeRecordByte6 {
			target = index
		}
	}
	if actor < 0 || target < 0 {
		t.Fatalf("map0 native actor/target anchors missing: actor=%d target=%d", actor, target)
	}
	groups, err := NativeAIScoredCommandCandidateGroups(
		st.W, st.H, records, len(st.Units), actor, 0, book[0],
		nativeCompositionBaseFlagsForTest(t, st),
		st.NativeTerrainMoveCodes, rows[0],
	)
	if err != nil {
		t.Fatal(err)
	}
	wantCell := Cell{X: int(records[target*nativeRecordSize]), Y: int(records[target*nativeRecordSize+1])}
	for _, group := range groups {
		if group.Destination != wantCell {
			continue
		}
		for _, index := range group.TargetIndices {
			if int(index) == target {
				return
			}
		}
	}
	t.Fatalf("map0 candidate at %v for target %d missing from %#v", wantCell, target, groups)
}
