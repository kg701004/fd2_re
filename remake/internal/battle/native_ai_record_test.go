package battle

import (
	"encoding/binary"
	"testing"
)

func completeNativeAIScoringUnit() *Unit {
	return &Unit{
		X: 99, Y: 98,
		NativeMapPresentation: NativeMapPresentationState{
			X: 7, Y: 8, Pose: 3, Motion: 4,
		},
		HasNativeMapPresentation: true,
		BattleFig:                9,
		HasBattleFig:             true,
		NativeIdentity:           10,
		HasNativeIdentity:        true,
		NativeRecordRace:         11,
		HasNativeRecordRace:      true,
		NativeRecordClass:        12,
		HasNativeRecordClass:     true,
		NativeRecordByte5:        0x20,
		HasNativeRecordByte5:     true,
		NativeRecordByte6:        1,
		HasNativeRecordByte6:     true,
		NativeRecordByte34:       0x81,
		HasNativeRecordByte34:    true,
		NativeRecordByte35:       13,
		HasNativeRecordByte35:    true,
		NativeRecordByte36:       14,
		HasNativeRecordByte36:    true,
		NativeRecordWord42:       234,
		HasNativeRecordWord42:    true,
		NativeRecordWord46:       18,
		HasNativeRecordWord46:    true,
		InventorySlots:           []int{1, 2, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags:     []int{0x40, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
		NativeCommandMask:        [5]byte{1, 2, 3, 4, 5},
		NativeTransient:          [6]byte{6, 7, 8, 9, 10, 0},
		Lv:                       15,
		MV:                       6,
		HP:                       123,
		MaxHP:                    234,
		MP:                       17,
		MaxMP:                    18,
		AP:                       19,
		DP:                       20,
		HIT:                      21,
		EV:                       22,
	}
}

func TestNativeAIScoringRecordsUsesRawPresentationAndAIBytes(t *testing.T) {
	unit := completeNativeAIScoringUnit()
	records, err := NativeAIScoringRecords([]*Unit{unit})
	if err != nil {
		t.Fatal(err)
	}
	if len(records) != nativeRecordSize {
		t.Fatalf("record len=%d want %d", len(records), nativeRecordSize)
	}
	if records[0] != 7 || records[1] != 8 || records[3] != 3 || records[4] != 4 ||
		records[5] != 0x20 || records[6] != 1 ||
		records[0x34] != 0x81 || records[0x35] != 13 || records[0x36] != 14 {
		t.Fatalf("raw AI fields were not preserved: %x", records[:0x37])
	}
	if got := binary.LittleEndian.Uint16(records[0x40:0x42]); got != 123 {
		t.Fatalf("raw HP=%d want 123", got)
	}
	if got := binary.LittleEndian.Uint16(records[0x42:0x44]); got != 234 {
		t.Fatalf("raw max HP=%d want 234", got)
	}
	if got := binary.LittleEndian.Uint16(records[0x46:0x48]); got != 18 {
		t.Fatalf("raw max MP=%d want 18", got)
	}
	records[0] = 0
	if unit.NativeMapPresentation.X != 7 {
		t.Fatal("returned record aliases runtime unit")
	}
}

func TestNativeAIScoringRecordsFailsClosedWithoutEveryProvenanceField(t *testing.T) {
	cases := []struct {
		name string
		drop func(*Unit)
	}{
		{"presentation", func(u *Unit) { u.HasNativeMapPresentation = false }},
		{"battle_fig", func(u *Unit) { u.HasBattleFig = false }},
		{"byte5", func(u *Unit) { u.HasNativeRecordByte5 = false }},
		{"byte34", func(u *Unit) { u.HasNativeRecordByte34 = false }},
		{"byte35", func(u *Unit) { u.HasNativeRecordByte35 = false }},
		{"byte36", func(u *Unit) { u.HasNativeRecordByte36 = false }},
		{"word42", func(u *Unit) { u.HasNativeRecordWord42 = false }},
		{"word46", func(u *Unit) { u.HasNativeRecordWord46 = false }},
		{"identity", func(u *Unit) { u.HasNativeIdentity = false }},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			unit := completeNativeAIScoringUnit()
			tc.drop(unit)
			if records, err := NativeAIScoringRecords([]*Unit{unit}); err == nil || records != nil {
				t.Fatalf("incomplete record accepted: len=%d err=%v", len(records), err)
			}
		})
	}
}

func TestMap0AssetsMaterializeNativeAIScoringRecords(t *testing.T) {
	st, err := Load("../../assets/maps/map0/map0_units.json")
	if err != nil {
		t.Fatal(err)
	}
	for index, unit := range st.Units {
		if err := unit.MaterializeNativeMapPresentation(); err != nil {
			t.Fatalf("unit %d presentation: %v", index, err)
		}
	}
	records, err := NativeAIScoringRecords(st.Units)
	if err != nil {
		t.Fatal(err)
	}
	if len(records) != len(st.Units)*nativeRecordSize {
		t.Fatalf("map0 records len=%d want %d", len(records), len(st.Units)*nativeRecordSize)
	}
	first := records[:nativeRecordSize]
	if first[0] != 1 || first[1] != 3 || first[5] != 0 ||
		first[6] != 0 || first[0x34] != 0 ||
		binary.LittleEndian.Uint16(first[0x40:0x42]) != 28 {
		t.Fatalf("map0 first native AI record has wrong anchors: %x", first[:0x44])
	}
}

func TestMap19AssetsCarryNativeAICommandMaskAndConstructorMP(t *testing.T) {
	st, err := Load("../../assets/maps/map19/map19_units.json")
	if err != nil {
		t.Fatal(err)
	}
	if len(st.Units) <= 55 {
		t.Fatalf("map19 roster len=%d", len(st.Units))
	}
	unit := st.Units[55]
	if unit.NativeIdentity != 92 || !unit.HasNativeIdentity ||
		unit.NativeCommandMask != ([5]byte{4, 0, 0, 8, 0}) ||
		!unit.HasNativeRecordWord46 || unit.NativeRecordWord46 != 288 ||
		unit.MP != 288 || unit.MaxMP != 288 {
		t.Fatalf("map19 unit55 raw AI inputs=%+v", unit)
	}
	book, err := LoadNativeCommandRecords("../../assets/spells.json")
	if err != nil {
		t.Fatal(err)
	}
	if got := NativeAvailableAIScoredCommandIDs(unit, book); len(got) != 2 ||
		got[0] != 2 || got[1] != 27 {
		t.Fatalf("map19 unit55 available commands=%v want [2 27]", got)
	}
	if err := unit.MaterializeNativeMapPresentation(); err != nil {
		t.Fatal(err)
	}
	records, err := NativeAIScoringRecords([]*Unit{unit})
	if err != nil {
		t.Fatal(err)
	}
	if got := binary.LittleEndian.Uint16(records[0x44:0x46]); got != 288 {
		t.Fatalf("map19 unit55 current MP=%d want 288", got)
	}
	if got := binary.LittleEndian.Uint16(records[0x46:0x48]); got != 288 {
		t.Fatalf("map19 unit55 max MP=%d want 288", got)
	}
}
