package battle

import "testing"

func TestSetNativeAIModeRangePreservesHighNibble(t *testing.T) {
	records := make([]byte, 3*nativeRecordSize)
	records[0x34] = 0x80
	records[nativeRecordSize+0x34] = 0xc2
	records[2*nativeRecordSize+0x34] = 0x45
	if err := SetNativeAIModeRange(records, 3, 0, 1, 7); err != nil {
		t.Fatal(err)
	}
	if records[0x34] != 0x87 || records[nativeRecordSize+0x34] != 0xc7 ||
		records[2*nativeRecordSize+0x34] != 0x45 {
		t.Fatalf("mode bytes=%#x/%#x/%#x",
			records[0x34], records[nativeRecordSize+0x34], records[2*nativeRecordSize+0x34])
	}
}

func TestSetNativeAIModeByteReplacesWholeByte(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x34] = 0xc2
	if err := SetNativeAIModeByte(records, 1, 0, 7); err != nil {
		t.Fatal(err)
	}
	if records[0x34] != 7 {
		t.Fatalf("mode byte=%#x", records[0x34])
	}
}

func TestNativeAIModeWritersRejectBounds(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	if err := SetNativeAIModeRange(records, 1, 0, 1, 2); err == nil {
		t.Fatal("out-of-range mode span accepted")
	}
	if err := SetNativeAIModeRange(records, 1, 0, 0, 0x10); err == nil {
		t.Fatal("wide mode accepted")
	}
	if err := SetNativeAIModeByte(records, 1, 1, 0); err == nil {
		t.Fatal("out-of-range mode unit accepted")
	}
}
