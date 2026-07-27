package battle

import (
	"encoding/binary"
	"testing"
)

func TestNativeType6And7ClearRecordMarkerRestoreHPConsumeSource(t *testing.T) {
	for _, tc := range []struct {
		typ          byte
		code, marker int
	}{
		{6, 20, 0x25},
		{7, 21, 0x26},
	} {
		records := make([]byte, 2*nativeRecordSize)
		binary.LittleEndian.PutUint16(records[0x40:0x42], 10)
		binary.LittleEndian.PutUint16(records[0x42:0x44], 100)
		records[tc.marker] = 3
		source := records[nativeRecordSize:]
		for slot := 0; slot < 8; slot++ {
			source[0x0a+slot*2], source[0x0b+slot*2] = 0, byte(0xc4+slot)
		}
		route, ok := NativeItemMarkerClearRestoreRouteForType(tc.typ)
		if !ok || route.PresentationCode != tc.code || route.MarkerOffset != tc.marker ||
			route.HPRestoreBase != 10 || !route.ConsumesSource {
			t.Fatalf("type %#x route = %#v, %v", tc.typ, route, ok)
		}
		result, nextRNG, _, err := ApplyNativeItemMarkerClearRestore(
			records, []byte{0}, route, 0, 1, 0,
		)
		if err != nil {
			t.Fatal(err)
		}
		if len(result) != 1 || !result[0].Applied || nextRNG == 0 ||
			records[tc.marker] != 0 || binary.LittleEndian.Uint16(records[0x40:0x42]) != 19 {
			t.Fatalf("type %#x result=%+v rng=%#x marker=%d hp=%d", tc.typ, result, nextRNG, records[tc.marker], binary.LittleEndian.Uint16(records[0x40:0x42]))
		}
		if source[0x0b] != 0xc5 || source[0x18] != 0x80 {
			t.Fatalf("type %#x source not consumed: %x", tc.typ, source[0x0a:0x1a])
		}
	}
}

func TestNativeMarkerClearRestorePreflightsSourceBeforeHP(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 10)
	binary.LittleEndian.PutUint16(records[0x42:0x44], 100)
	records[0x25] = 2
	before := append([]byte(nil), records...)
	route, _ := NativeItemMarkerClearRestoreRouteForType(6)
	if _, _, _, err := ApplyNativeItemMarkerClearRestore(records, []byte{0}, route, 0, 0, 8); err == nil {
		t.Fatal("invalid source slot unexpectedly accepted")
	}
	if string(records) != string(before) {
		t.Fatal("invalid source removal partially mutated target")
	}
}
