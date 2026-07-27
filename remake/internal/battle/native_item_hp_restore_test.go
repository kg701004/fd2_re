package battle

import (
	"encoding/binary"
	"testing"
)

func TestNativeType5HPRestoreConsumesSourceAfterMutation(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 10)
	binary.LittleEndian.PutUint16(records[0x42:0x44], 100)
	for slot := 0; slot < 8; slot++ {
		off := nativeRecordSize + 0x0a + slot*2
		records[off], records[off+1] = 0, byte(0xc0+slot)
	}
	route, ok := NativeItemHPRestoreRouteForType(5, 40)
	if !ok {
		t.Fatal("type 5 route missing")
	}
	result, err := ApplyNativeItemHPRestore(records, []byte{0}, route, 0, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Results) != 1 || binary.LittleEndian.Uint16(records[0x40:0x42]) <= 10 {
		t.Fatalf("restore result=%+v hp=%d", result, binary.LittleEndian.Uint16(records[0x40:0x42]))
	}
	source := records[nativeRecordSize:]
	if source[0x0c+1] != 0xc2 || source[0x18] != 0x80 {
		t.Fatalf("type 5 source slot not consumed: %x", source[0x0a:0x1a])
	}
}

func TestNativeType13HPRestoreRetainsSource(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 10)
	binary.LittleEndian.PutUint16(records[0x42:0x44], 100)
	records[0x0a], records[0x0b] = 0x40, 0xd3
	beforeInventory := append([]byte(nil), records[0x0a:0x1a]...)
	route, ok := NativeItemHPRestoreRouteForType(13, 200)
	if !ok {
		t.Fatal("type 13 route missing")
	}
	if _, err := ApplyNativeItemHPRestore(records, []byte{0}, route, 0, -1, -1); err != nil {
		t.Fatal(err)
	}
	if string(records[0x0a:0x1a]) != string(beforeInventory) {
		t.Fatalf("type 13 unexpectedly consumed source: %x", records[0x0a:0x1a])
	}
}

func TestNativeItemHPRestorePreflightsRemovalAtomically(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 10)
	binary.LittleEndian.PutUint16(records[0x42:0x44], 100)
	before := append([]byte(nil), records...)
	route, _ := NativeItemHPRestoreRouteForType(5, 40)
	if _, err := ApplyNativeItemHPRestore(records, []byte{0}, route, 0, 0, 8); err == nil {
		t.Fatal("invalid source slot unexpectedly accepted")
	}
	if string(records) != string(before) {
		t.Fatal("invalid source removal partially restored HP")
	}
}
