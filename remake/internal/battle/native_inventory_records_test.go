package battle

import "testing"

func TestNativeInventoryRecordsMaterializesOnlyProvenCells(t *testing.T) {
	u := &Unit{InventorySlots: []int{0x64, 0xff, 2, 3, 4, 5, 6, 7}, NativeInventoryFlags: []int{0, 0x80, 0, 0, 0, 0, 0, 0x80}}
	records, err := NativeInventoryRecords([]*Unit{u}, 1)
	if err != nil {
		t.Fatal(err)
	}
	if records[0x0a] != 0 || records[0x0b] != 0x64 || records[0x0a+2] != 0x80 || records[0x0b+2] != 0xff {
		t.Fatalf("raw inventory cells=%#x %#x %#x %#x", records[0x0a], records[0x0b], records[0x0a+2], records[0x0b+2])
	}
	if got, err := FindNativeInventoryItemInUnit(records, 0, 0x64); err != nil || got != 0 {
		t.Fatalf("native search got=%d err=%v", got, err)
	}
}

func TestNativeInventoryRecordsFailsClosedWithoutProvenance(t *testing.T) {
	if _, err := NativeInventoryRecords([]*Unit{{Inventory: []int{0x64}}}, 1); err == nil {
		t.Fatal("normalized-only inventory must not be serialized as raw")
	}
}
