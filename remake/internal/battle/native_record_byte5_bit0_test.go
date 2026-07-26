package battle

import "testing"

func TestNativeRecordByte5Bit0MasksOnlyLowBit(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[5] = 0xff
	records[nativeRecordSize+5] = 0xfe
	if got, err := NativeRecordByte5Bit0(records, 0); err != nil || got != 1 {
		t.Fatalf("record0=(%d,%v), want (1,nil)", got, err)
	}
	if got, err := NativeRecordByte5Bit0(records, 1); err != nil || got != 0 {
		t.Fatalf("record1=(%d,%v), want (0,nil)", got, err)
	}
}

func TestNativeRecordByte5Bit0RejectsBounds(t *testing.T) {
	if _, err := NativeRecordByte5Bit0(make([]byte, nativeRecordSize), 1); err == nil {
		t.Fatal("out-of-range record unexpectedly accepted")
	}
}
