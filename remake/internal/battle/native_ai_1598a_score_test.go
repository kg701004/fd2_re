package battle

import "testing"

func TestScoreNativeAI1598ARejectsAllZeroWinner(t *testing.T) {
	unit := completeNativeAIScoringUnit()
	unit.NativeCommandMask = [5]byte{0, 0, 0, 1, 0}
	unit.NativeMapPresentation.X = 0
	unit.NativeMapPresentation.Y = 0
	unit.MP = 255
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[24] = NativeCommandRecord{
		ID: 24, SelectionMode: 0, EffectMode: 0, TargetCode: 1,
	}
	records, err := NativeAIScoringRecords([]*Unit{unit})
	if err != nil {
		t.Fatal(err)
	}
	got, err := ScoreNativeAI1598A(
		1, 1, records, 1, 0, 1, unit, book,
		[]byte{0}, []byte{0}, make([]byte, NativeMovementCostRowSize), nil,
	)
	if err != nil {
		t.Fatal(err)
	}
	if got.MaxScore != 0 || got.HasPositiveWinner {
		t.Fatalf("all-zero result invented winner: %+v", got)
	}
}

func TestScoreNativeAI1598AFailsClosedWhenActorRecordDisagrees(t *testing.T) {
	unit := completeNativeAIScoringUnit()
	unit.NativeMapPresentation.X = 0
	unit.NativeMapPresentation.Y = 0
	records, err := NativeAIScoringRecords([]*Unit{unit})
	if err != nil {
		t.Fatal(err)
	}
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	unit.MP++
	if _, err := ScoreNativeAI1598A(
		1, 1, records, 1, 0, 0, unit, book,
		[]byte{0}, []byte{0}, make([]byte, NativeMovementCostRowSize), nil,
	); err == nil {
		t.Fatal("actor MP/record mismatch was accepted")
	}
}

func TestMap0AssetsProducePositiveNativeAI1598AScoreForCommand0(t *testing.T) {
	st, err := Load("../../assets/maps/map0/map0_units.json")
	if err != nil {
		t.Fatal(err)
	}
	actor := 23
	if st.Units[actor].NativeIdentity != 103 {
		t.Fatalf("map0 actor identity=%d want 103", st.Units[actor].NativeIdentity)
	}
	st.Units[actor].NativeCommandMask = [5]byte{1, 0, 0, 0, 0}
	st.Units[actor].MP = 255
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
	got, err := ScoreNativeAI1598A(
		st.W, st.H, records, len(st.Units), actor, 0, st.Units[actor], book,
		st.NativeTargetFlags, st.NativeTerrainMoveCodes, rows[0], nil,
	)
	if err != nil {
		t.Fatal(err)
	}
	if !got.HasPositiveWinner || got.MaxScore != 96 {
		t.Fatalf("map0 command0 native score=%+v", got)
	}
	if got.PositiveWinner.CommandID != 0 ||
		got.PositiveWinner.X != 23 || got.PositiveWinner.Y != 14 {
		t.Fatalf("map0 command0 native winner=%+v", got)
	}
}
