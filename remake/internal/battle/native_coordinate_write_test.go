package battle

import "testing"

func TestSetNativeUnitCoordinateBytesWritesRawRecordPrefix(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	if err := SetNativeUnitCoordinateBytes(records, 1, 0x21, 0x37); err != nil {
		t.Fatal(err)
	}
	if records[nativeRecordSize] != 0x21 || records[nativeRecordSize+1] != 0x37 {
		t.Fatalf("coords = %#x %#x", records[nativeRecordSize], records[nativeRecordSize+1])
	}
}

func TestSetNativeUnitCoordinateBytesRejectsBadUnitBeforeWrite(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	if err := SetNativeUnitCoordinateBytes(records, 1, 1, 2); err == nil {
		t.Fatal("expected bad unit index")
	}
	if records[0] != 0 || records[1] != 0 {
		t.Fatal("bad input mutated record")
	}
}
