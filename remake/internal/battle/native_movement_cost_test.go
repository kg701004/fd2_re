package battle

import (
	"testing"
)

func nativeMovementRowsForTest() [][]byte {
	rows := make([][]byte, NativeMovementCostRowCount)
	for selector := range rows {
		rows[selector] = make([]byte, NativeMovementCostRowSize)
	}
	return rows
}

func TestNativeRelocationDestinationAllowedMatchesMode6Gates(t *testing.T) {
	records := make([]byte, 3*nativeRecordSize)
	target := records[nativeRecordSize : 2*nativeRecordSize]
	target[0], target[1], target[0x20] = 4, 5, 9
	rows := nativeMovementRowsForTest()
	rows[9][3] = 20
	allowed, err := NativeRelocationDestinationAllowed(records, 3, 1, 8, 9, 3, rows)
	if err != nil || !allowed {
		t.Fatalf("allowed=%v err=%v", allowed, err)
	}

	occupant := records[2*nativeRecordSize:]
	occupant[0], occupant[1], occupant[5] = 8, 9, 0
	if allowed, err = NativeRelocationDestinationAllowed(records, 3, 1, 8, 9, 3, rows); err != nil || allowed {
		t.Fatalf("occupied allowed=%v err=%v", allowed, err)
	}
	occupant[5] = 1
	if allowed, err = NativeRelocationDestinationAllowed(records, 3, 1, 8, 9, 3, rows); err != nil || !allowed {
		t.Fatalf("bit0 occupant allowed=%v err=%v", allowed, err)
	}
	rows[9][3] = 19
	if allowed, err = NativeRelocationDestinationAllowed(records, 3, 1, 8, 9, 3, rows); err != nil || allowed {
		t.Fatalf("wrong terrain code allowed=%v err=%v", allowed, err)
	}
}

func TestNativeRelocationDestinationSelectorOverrides(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	rows := nativeMovementRowsForTest()
	rows[1][2], rows[19][2] = 20, 20
	for _, tc := range []struct {
		name                 string
		unit7, race, classID byte
		wantSelector         int
	}{
		{"unit7", 0x1c, 4, 0x13, 1},
		{"class", 0, 0, 0x13, 19},
		{"race4", 0, 4, 3, 19},
		{"race5", 0, 5, 3, 19},
	} {
		t.Run(tc.name, func(t *testing.T) {
			record := records[:nativeRecordSize]
			for i := range record {
				record[i] = 0
			}
			record[0x07], record[0x1f], record[0x20] = tc.unit7, tc.race, tc.classID
			allowed, err := NativeRelocationDestinationAllowed(records, 1, 0, 1, 1, 2, rows)
			if err != nil || !allowed || rows[tc.wantSelector][2] != 20 {
				t.Fatalf("allowed=%v err=%v", allowed, err)
			}
		})
	}
}

func TestLoadNativeMovementCostRowsFixture(t *testing.T) {
	rows, err := LoadNativeMovementCostRows("../../assets/data/native_movement_cost_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 29 || len(rows[0]) != 20 {
		t.Fatalf("shape=%d/%d", len(rows), len(rows[0]))
	}
	for column, value := range rows[0] {
		if value != 1 {
			t.Fatalf("row0[%d]=%d want1", column, value)
		}
	}
	if rows[1][2] != 20 || rows[1][6] != 20 {
		t.Fatalf("row1 anchors=%d/%d", rows[1][2], rows[1][6])
	}
}
