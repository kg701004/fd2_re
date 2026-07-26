package battle

import "testing"

func TestAssignNativeReservedItemConsumesFirstReservedCell(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x0a], records[0x0e] = 0x80, 0x80
	records[0x0b], records[0x0f] = 0x11, 0x22
	ok, err := AssignNativeReservedItem(records, 0, 0xc4)
	if err != nil || !ok {
		t.Fatalf("assign ok=%v err=%v", ok, err)
	}
	if records[0x0a] != 0 || records[0x0b] != 0xc4 || records[0x0e] != 0x80 || records[0x0f] != 0x22 {
		t.Fatalf("cells=%#x %#x %#x %#x", records[0x0a], records[0x0b], records[0x0e], records[0x0f])
	}
}

func TestAssignNativeReservedItemReturnsFalseWhenNoReservedCell(t *testing.T) {
	ok, err := AssignNativeReservedItem(make([]byte, nativeRecordSize), 0, 9)
	if err != nil || ok {
		t.Fatalf("ok=%v err=%v, want false/nil", ok, err)
	}
}
