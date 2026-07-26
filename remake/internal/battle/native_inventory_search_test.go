package battle

import "testing"

func TestFindNativeInventoryItemUsesRawPrefixAndDoesNotMutate(t *testing.T) {
	records := make([]byte, 16*nativeRecordSize)
	base := 3 * nativeRecordSize
	// Three clear flags make the native search prefix length three.
	records[base+0x0a] = 0
	records[base+0x0b] = 0x64
	records[base+0x0c] = 0
	records[base+0x0d] = 0x21
	records[base+0x0e] = 0
	records[base+0x0f] = 0x37
	// A matching item after the native prefix must not be found.
	records[base+0x10] = 0x80
	records[base+0x11] = 0x64
	before := append([]byte(nil), records...)
	unit, slot, err := FindNativeInventoryItem(records, 0x64)
	if err != nil || unit != 3 || slot != 0 {
		t.Fatalf("got (%d,%d,%v), want (3,0,nil)", unit, slot, err)
	}
	if string(records) != string(before) {
		t.Fatal("native inventory search mutated records")
	}
}

func TestFindNativeInventoryItemMissingAndBounds(t *testing.T) {
	records := make([]byte, 16*nativeRecordSize)
	unit, slot, err := FindNativeInventoryItem(records, 0x64)
	if err != nil || unit != -1 || slot != -1 {
		t.Fatalf("missing got (%d,%d,%v), want (-1,-1,nil)", unit, slot, err)
	}
	if _, err := FindNativeInventoryItemInUnit(make([]byte, nativeRecordSize), 1, 1); err == nil {
		t.Fatal("short unit record unexpectedly accepted")
	}
	if _, _, err := FindNativeInventoryItem(make([]byte, 16*nativeRecordSize-1), 1); err == nil {
		t.Fatal("short 16-slot buffer unexpectedly accepted")
	}
}

func TestFindNativeInventoryItemInUnitRespectsFreePrefixCount(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	base := 0
	for slot := 0; slot < 8; slot++ {
		records[base+0x0a+slot*2] = 0x80
		records[base+0x0b+slot*2] = 0x64
	}
	// All flags occupied => 0x1b8a6 returns zero, so 0x31860 does not scan.
	got, err := FindNativeInventoryItemInUnit(records, 0, 0x64)
	if err != nil || got != -1 {
		t.Fatalf("got (%d,%v), want (-1,nil)", got, err)
	}
}
