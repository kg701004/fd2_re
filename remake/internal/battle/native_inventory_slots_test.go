package battle

import "testing"

func TestNativeInventoryOccupiedCountUsesFlagBytesOnly(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	for slot := 0; slot < 8; slot++ {
		records[0x0a+slot*2+1] = 0xff // item bytes must not affect availability
	}
	records[0x0a], records[0x0a+4], records[0x0a+14] = 0x80, 0x80, 0x80
	occupied, err := NativeInventoryOccupiedCount(records, 0)
	if err != nil || occupied != 5 {
		t.Fatalf("occupied=%d err=%v, want 5", occupied, err)
	}
}

func TestNativeInventoryOccupiedCountFailsClosed(t *testing.T) {
	if _, err := NativeInventoryOccupiedCount(make([]byte, nativeRecordSize), 1); err == nil {
		t.Fatal("missing record must fail")
	}
}
