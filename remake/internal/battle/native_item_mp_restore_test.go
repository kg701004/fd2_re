package battle

import (
	"encoding/binary"
	"testing"
)

func TestNativeType11MPRestoreSkipsZeroMaxWithoutRNGAndConsumesSource(t *testing.T) {
	records := make([]byte, 3*nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x44:0x46], 0)
	binary.LittleEndian.PutUint16(records[0x46:0x48], 0)
	second := records[nativeRecordSize:]
	binary.LittleEndian.PutUint16(second[0x44:0x46], 10)
	binary.LittleEndian.PutUint16(second[0x46:0x48], 100)
	source := records[2*nativeRecordSize:]
	for slot := 0; slot < 8; slot++ {
		source[0x0a+slot*2], source[0x0b+slot*2] = 0, byte(0xce+slot)
	}
	route, ok := NativeItemMPRestoreRouteForType(11, 80)
	if !ok {
		t.Fatal("type 11 route missing")
	}
	result, err := ApplyNativeItemMPRestore(records, []byte{0, 1}, route, 0, 2, 0)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.SkippedTargets) != 1 || result.SkippedTargets[0] != 0 || len(result.Results) != 1 {
		t.Fatalf("result=%+v", result)
	}
	if result.RNGState != result.Results[0].RNGState || result.RNGState == 0 {
		t.Fatalf("zero-max target consumed RNG: %+v", result)
	}
	if binary.LittleEndian.Uint16(second[0x44:0x46]) <= 10 {
		t.Fatalf("MP was not restored: %d", binary.LittleEndian.Uint16(second[0x44:0x46]))
	}
	if source[0x0b] != 0xcf || source[0x18] != 0x80 {
		t.Fatalf("source slot not consumed: %x", source[0x0a:0x1a])
	}
}

func TestNativeType11MPRestorePreflightsSourceAtomically(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x44:0x46], 10)
	binary.LittleEndian.PutUint16(records[0x46:0x48], 100)
	before := append([]byte(nil), records...)
	route, _ := NativeItemMPRestoreRouteForType(11, 80)
	if _, err := ApplyNativeItemMPRestore(records, []byte{0}, route, 0, 0, 8); err == nil {
		t.Fatal("invalid source slot unexpectedly accepted")
	}
	if string(records) != string(before) {
		t.Fatal("invalid source removal partially restored MP")
	}
}
