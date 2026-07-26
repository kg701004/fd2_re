package battle

import "testing"

func TestRemoveNativeInventorySlotShiftsRawCellsAndMarksTailFree(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	for slot := 0; slot < 8; slot++ {
		off := 0x0a + slot*2
		records[off] = byte(slot)
		records[off+1] = byte(0xa0 + slot)
	}
	if err := RemoveNativeInventorySlot(records, 0, 2); err != nil {
		t.Fatal(err)
	}
	for slot := 2; slot < 7; slot++ {
		off := 0x0a + slot*2
		if records[off] != byte(slot+1) || records[off+1] != byte(0xa0+slot+1) {
			t.Fatalf("slot %d = %#x %#x", slot, records[off], records[off+1])
		}
	}
	if records[0x18] != 0x80 || records[0x19] != 0xa7 {
		t.Fatalf("tail = %#x %#x", records[0x18], records[0x19])
	}
}

func TestRemoveNativeInventorySlotKeepsTailItemByteForLastSlot(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x18], records[0x19] = 0x40, 0xd3
	if err := RemoveNativeInventorySlot(records, 0, 7); err != nil {
		t.Fatal(err)
	}
	if records[0x18] != 0x80 || records[0x19] != 0xd3 {
		t.Fatalf("tail = %#x %#x", records[0x18], records[0x19])
	}
}

func TestRemoveNativeInventorySlotRejectsInvalidInput(t *testing.T) {
	if err := RemoveNativeInventorySlot(make([]byte, nativeRecordSize), 0, 8); err == nil {
		t.Fatal("expected invalid slot to fail closed")
	}
	if err := RemoveNativeInventorySlot(make([]byte, 0x1a-1), 0, 0); err == nil {
		t.Fatal("expected short record to fail closed")
	}
}
