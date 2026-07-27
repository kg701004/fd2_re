package battle

import (
	"encoding/binary"
	"testing"
)

func TestNativeType17And18IncreaseMaxCapacityAndConsumeSource(t *testing.T) {
	for _, tc := range []struct {
		typ           byte
		stat          NativeItemCapacityStat
		offset, start int
	}{
		{17, NativeItemMaxHP, 0x42, 100},
		{18, NativeItemMaxMP, 0x46, 50},
	} {
		records := make([]byte, 2*nativeRecordSize)
		binary.LittleEndian.PutUint16(records[tc.offset:], uint16(tc.start))
		source := records[nativeRecordSize:]
		for slot := 0; slot < 8; slot++ {
			source[0x0a+slot*2], source[0x0b+slot*2] = 0, byte(0xd0+slot)
		}
		route, ok := NativeItemCapacityStepRouteForType(tc.typ, 20)
		if !ok || route.Stat != tc.stat || !route.ConsumesSource {
			t.Fatalf("type %#x route = %#v, %v", tc.typ, route, ok)
		}
		got, err := ApplyNativeItemCapacityStep(records, 0, route, 1, 0)
		if err != nil {
			t.Fatal(err)
		}
		if got != uint16(tc.start+20) || binary.LittleEndian.Uint16(records[tc.offset:]) != got {
			t.Fatalf("type %#x result=%d raw=%d", tc.typ, got, binary.LittleEndian.Uint16(records[tc.offset:]))
		}
		if source[0x0b] != 0xd1 || source[0x18] != 0x80 {
			t.Fatalf("type %#x source not consumed: %x", tc.typ, source[0x0a:0x1a])
		}
	}
}

func TestNativeType19IncreasesMVAndPreservesEXP(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[0x3b], records[0x3c] = 7, 99
	source := records[nativeRecordSize:]
	source[0x0a], source[0x0b] = 0, 96
	route, ok := NativeItemCapacityStepRouteForType(19, 1)
	if !ok || route.Stat != NativeItemMV {
		t.Fatalf("type 19 route = %#v, %v", route, ok)
	}
	got, err := ApplyNativeItemCapacityStep(records, 0, route, 1, 0)
	if err != nil {
		t.Fatal(err)
	}
	if got != 8 || records[0x3b] != 8 || records[0x3c] != 99 || source[0x18] != 0x80 {
		t.Fatalf("result=%d mv=%d exp=%d inventory=%x", got, records[0x3b], records[0x3c], source[0x0a:0x1a])
	}
}

func TestNativeCapacityStepPreflightsSourceBeforeMutation(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x42:], 100)
	route, _ := NativeItemCapacityStepRouteForType(17, 20)
	if _, err := ApplyNativeItemCapacityStep(records, 0, route, 0, 8); err == nil {
		t.Fatal("invalid source slot unexpectedly accepted")
	}
	if binary.LittleEndian.Uint16(records[0x42:]) != 100 {
		t.Fatal("invalid source removal partially mutated max HP")
	}
}
