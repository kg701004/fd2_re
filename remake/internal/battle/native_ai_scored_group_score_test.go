package battle

import (
	"encoding/binary"
	"reflect"
	"testing"
)

func TestScoreNativeAIScoredCommandGroupsDispatchesAttackAndKeepsOrder(t *testing.T) {
	records := make([]byte, 3*nativeRecordSize)
	binary.LittleEndian.PutUint16(records[nativeRecordSize+0x40:], 20)
	binary.LittleEndian.PutUint16(records[2*nativeRecordSize+0x40:], 80)
	records[nativeRecordSize+8] = 1
	records[2*nativeRecordSize+8] = 1
	groups := []NativeAIScoredCommandCandidateGroup{
		{Destination: Cell{X: 2, Y: 1}, TargetIndices: []byte{2}},
		{Destination: Cell{X: 1, Y: 1}, TargetIndices: []byte{1, 2}},
	}
	got, err := ScoreNativeAIScoredCommandGroups(records, 2, 50, groups, nil)
	if err != nil {
		t.Fatal(err)
	}
	want := []NativeAIScoredCommandGroupScore{
		{Destination: Cell{X: 2, Y: 1}, TargetIndices: []byte{2}, Score: 8},
		{Destination: Cell{X: 1, Y: 1}, TargetIndices: []byte{1, 2}, Score: 32},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("scores=%#v want=%#v", got, want)
	}
}

func TestScoreNativeAIScoredCommandGroupsDispatchesRecoveryAndZeroFamilies(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:], 10)
	binary.LittleEndian.PutUint16(records[0x42:], 60)
	groups := []NativeAIScoredCommandCandidateGroup{{
		Destination: Cell{}, TargetIndices: []byte{0},
	}}
	recovery, err := ScoreNativeAIScoredCommandGroups(records, 13, 0, groups, nil)
	if err != nil || len(recovery) != 1 || recovery[0].Score != 8 {
		t.Fatalf("recovery=%#v err=%v", recovery, err)
	}
	zero, err := ScoreNativeAIScoredCommandGroups(records, 28, 0, groups, nil)
	if err != nil || len(zero) != 1 || zero[0].Score != 0 {
		t.Fatalf("zero family=%#v err=%v", zero, err)
	}
}

func TestScoreNativeAIScoredCommandGroupsRequiresGateForIDs10To12(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	groups := []NativeAIScoredCommandCandidateGroup{{
		Destination: Cell{}, TargetIndices: []byte{0},
	}}
	if _, err := ScoreNativeAIScoredCommandGroups(records, 10, 1, groups, nil); err == nil {
		t.Fatal("command 10 accepted without 0x1f183 gate")
	}
}

func TestScoreNativeAIScoredCommandGroupsReturnsDetachedTargets(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	group := NativeAIScoredCommandCandidateGroup{
		Destination: Cell{}, TargetIndices: []byte{0},
	}
	got, err := ScoreNativeAIScoredCommandGroups(records, 28, 0, []NativeAIScoredCommandCandidateGroup{group}, nil)
	if err != nil {
		t.Fatal(err)
	}
	got[0].TargetIndices[0] = 9
	if group.TargetIndices[0] != 0 {
		t.Fatal("score result aliases candidate group targets")
	}
}

func TestMap0AssetsScoreNativeAIScoredCommandGroup(t *testing.T) {
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
	actor := -1
	for index, unit := range st.Units {
		if unit.NativeIdentity == 103 && unit.HasNativeIdentity {
			actor = index
			break
		}
	}
	if actor < 0 {
		t.Fatal("map0 identity 103 actor missing")
	}
	groups, err := NativeAIScoredCommandCandidateGroups(
		st.W, st.H, records, len(st.Units), actor, 0, book[0],
		st.NativeTargetFlags, st.NativeTerrainMoveCodes, rows[0],
	)
	if err != nil {
		t.Fatal(err)
	}
	scores, err := ScoreNativeAIScoredCommandGroups(
		records, book[0].ID, book[0].Damage, groups, nil,
	)
	if err != nil {
		t.Fatal(err)
	}
	for _, score := range scores {
		if score.Destination == (Cell{X: 23, Y: 14}) {
			if len(score.TargetIndices) != 4 || score.Score != 96 {
				t.Fatalf("map0 ally group targets=%v score=%d want four/96", score.TargetIndices, score.Score)
			}
			return
		}
	}
	t.Fatalf("map0 scored ally destination missing: %#v", scores)
}
