package battle

import (
	"encoding/binary"
	"testing"
)

func TestNativeType12AddsHITEVAndRetainsSourceContract(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x4c:0x4e], 90)
	binary.LittleEndian.PutUint16(records[0x4e:0x50], 5)
	second := records[nativeRecordSize:]
	second[0x24] = 3
	binary.LittleEndian.PutUint16(second[0x4c:0x4e], 80)
	binary.LittleEndian.PutUint16(second[0x4e:0x50], 10)
	route, ok := NativeItemHITEVStepRouteForType(12)
	if !ok || route.ConsumesSource {
		t.Fatalf("type 12 route = %#v, %v", route, ok)
	}
	result, nextRNG, _, err := ApplyNativeItemHITEVStep(records, []byte{0, 1}, route, 0)
	if err != nil {
		t.Fatal(err)
	}
	if len(result) != 2 || !result[0].Processed || result[1].Processed || nextRNG == 0 {
		t.Fatalf("result=%+v rng=%#x", result, nextRNG)
	}
	if got := binary.LittleEndian.Uint16(records[0x4c:0x4e]); got != 105 {
		t.Fatalf("HIT = %d, want 105", got)
	}
	if got := binary.LittleEndian.Uint16(records[0x4e:0x50]); got != 20 {
		t.Fatalf("EV = %d, want 20", got)
	}
	if got := binary.LittleEndian.Uint16(second[0x4c:0x4e]); got != 80 {
		t.Fatalf("marked target HIT changed to %d", got)
	}
}
