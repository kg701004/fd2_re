package battle

import "testing"

func TestSetNativeRecordByte5OneOverwritesWholeByte(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[5] = 0x80
	records[nativeRecordSize+5] = 0xff
	if err := SetNativeRecordByte5One(records, 1); err != nil {
		t.Fatal(err)
	}
	if records[5] != 0x80 || records[nativeRecordSize+5] != 1 {
		t.Fatalf("bytes=%#x/%#x, want %#x/1", records[5], records[nativeRecordSize+5], 0x80)
	}
}

func TestSetNativeRecordByte5OneRejectsBounds(t *testing.T) {
	if err := SetNativeRecordByte5One(make([]byte, nativeRecordSize), 1); err == nil {
		t.Fatal("out-of-range record unexpectedly accepted")
	}
	if err := SetNativeRecordByte5One(make([]byte, nativeRecordSize), -1); err == nil {
		t.Fatal("negative record unexpectedly accepted")
	}
}
