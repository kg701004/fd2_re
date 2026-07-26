package battle

import "testing"

func TestNativeRecordBit7SetAndClearPreserveOtherBits(t *testing.T) {
	records := make([]byte, 2*0x50)
	records[5], records[0x50+5] = 0x01, 0xff
	if err := SetNativeRecordBit7(records, 1); err != nil {
		t.Fatal(err)
	}
	if records[5] != 0x01 || records[0x50+5] != 0xff {
		t.Fatalf("set touched wrong bytes: %#x %#x", records[5], records[0x50+5])
	}
	if err := ClearNativeRecordBit7All(records, 2); err != nil {
		t.Fatal(err)
	}
	if records[5] != 0x01 || records[0x50+5] != 0x7f {
		t.Fatalf("clear result=%#x %#x", records[5], records[0x50+5])
	}
}

func TestNativeRecordFlagsFailClosedOnShortBuffers(t *testing.T) {
	if err := SetNativeRecordBit7(make([]byte, 0x50), 1); err == nil {
		t.Fatal("out-of-range set must fail")
	}
	if err := ClearNativeRecordBit7All(make([]byte, 0x4f), 1); err == nil {
		t.Fatal("short clear buffer must fail")
	}
}
