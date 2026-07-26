package battle

import "testing"

func TestNativeInventoryFreeSlotCountUsesFlagBytesOnly(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	for slot := 0; slot < 8; slot++ {
		records[0x0a+slot*2+1] = 0xff // item bytes must not affect availability
	}
	records[0x0a], records[0x0a+4], records[0x0a+14] = 0x80, 0x80, 0x80
	free, err := NativeInventoryFreeSlotCount(records, 0)
	if err != nil || free != 5 {
		t.Fatalf("free=%d err=%v, want 5", free, err)
	}
}

func TestNativeInventoryFreeSlotCountFailsClosed(t *testing.T) {
	if _, err := NativeInventoryFreeSlotCount(make([]byte, nativeRecordSize), 1); err == nil {
		t.Fatal("missing record must fail")
	}
}
