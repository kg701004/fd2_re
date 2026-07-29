package battle

import "testing"

func TestNativeBattleResultCode205B4KeepsZeroForAnyActiveRawCampZero(t *testing.T) {
	records := make([]byte, 3*nativeRecordSize)
	records[6] = 1
	records[nativeRecordSize+6] = 0
	records[nativeRecordSize+5] = 0
	records[2*nativeRecordSize+6] = 0
	records[2*nativeRecordSize+5] = 1

	got, err := NativeBattleResultCode205B4(records, 3)
	if err != nil || got != 0 {
		t.Fatalf("result=(%d,%v), want (0,nil)", got, err)
	}
}

func TestNativeBattleResultCode205B4ReturnsTwoWithoutActiveRawCampZero(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[6] = 1
	records[nativeRecordSize+6] = 0
	records[nativeRecordSize+5] = 1

	got, err := NativeBattleResultCode205B4(records, 2)
	if err != nil || got != 2 {
		t.Fatalf("result=(%d,%v), want (2,nil)", got, err)
	}
}

func TestNativeBattleResultCode205B4RecordZeroBitOverridesWithOne(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[5] = 1
	records[6] = 1
	records[nativeRecordSize+6] = 0
	records[nativeRecordSize+5] = 0

	got, err := NativeBattleResultCode205B4(records, 2)
	if err != nil || got != 1 {
		t.Fatalf("result=(%d,%v), want (1,nil)", got, err)
	}
}

func TestNativeBattleResultCode205B4IgnoresRawBitSeven(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[6] = 1
	records[nativeRecordSize+6] = 0
	records[nativeRecordSize+5] = 0x80

	got, err := NativeBattleResultCode205B4(records, 2)
	if err != nil || got != 0 {
		t.Fatalf("result=(%d,%v), want (0,nil)", got, err)
	}
}

func TestNativeBattleResultCode205B4RejectsMalformedRecords(t *testing.T) {
	for _, tc := range []struct {
		records []byte
		count   int
	}{
		{nil, 0},
		{make([]byte, nativeRecordSize-1), 1},
		{make([]byte, nativeRecordSize), 2},
	} {
		if _, err := NativeBattleResultCode205B4(tc.records, tc.count); err == nil {
			t.Fatalf("accepted malformed count=%d bytes=%d", tc.count, len(tc.records))
		}
	}
}

func TestMap0AssetsAnchorNativeBattleResultCode205B4(t *testing.T) {
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
	got, err := NativeBattleResultCode205B4(records, len(st.Units))
	if err != nil || got != 0 {
		t.Fatalf("map0 result=(%d,%v), want (0,nil)", got, err)
	}
}
