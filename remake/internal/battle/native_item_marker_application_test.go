package battle

import (
	"encoding/binary"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func findMarkerApplicationSeed(t *testing.T, succeeds bool) uint16 {
	t.Helper()
	for seed := 0; seed <= 0xffff; seed++ {
		if (fdother.NativeRNGStep(uint16(seed))%100 < 50) == succeeds {
			return uint16(seed)
		}
	}
	t.Fatalf("no RNG seed found for succeeds=%v", succeeds)
	return 0
}

func TestNativeType14And22MarkerRoutesRetainSourceContract(t *testing.T) {
	for _, tc := range []struct {
		typ          byte
		code, marker int
	}{
		{14, 27, 0x26},
		{22, 22, 0x27},
	} {
		records := make([]byte, nativeRecordSize)
		binary.LittleEndian.PutUint16(records[0x40:0x42], 100)
		route, ok := NativeItemMarkerApplicationRouteForType(tc.typ)
		if !ok || route.PresentationCode != tc.code || route.MarkerOffset != tc.marker ||
			route.HPDamageBase != 10 || route.ConsumesSource {
			t.Fatalf("type %#x route = %#v, %v", tc.typ, route, ok)
		}
		result, nextRNG, _, err := ApplyNativeItemMarkerApplication(
			records, []byte{0}, route, findMarkerApplicationSeed(t, true),
		)
		if err != nil {
			t.Fatal(err)
		}
		if len(result) != 1 || !result[0].Applied || result[0].Damage.Rolled < 9 ||
			result[0].Damage.Rolled > 10 || nextRNG == 0 ||
			binary.LittleEndian.Uint16(records[0x40:0x42]) != uint16(100-result[0].Damage.Actual) ||
			records[tc.marker] == 0 {
			t.Fatalf("type %#x result=%+v rng=%#x hp=%d marker=%d", tc.typ, result, nextRNG, binary.LittleEndian.Uint16(records[0x40:0x42]), records[tc.marker])
		}
	}
}

func TestNativeMarkerApplicationFailedGateUsesOneRNGAndNoMutation(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 100)
	route, _ := NativeItemMarkerApplicationRouteForType(14)
	seed := findMarkerApplicationSeed(t, false)
	result, nextRNG, _, err := ApplyNativeItemMarkerApplication(records, []byte{0}, route, seed)
	if err != nil {
		t.Fatal(err)
	}
	if result[0].Applied || nextRNG != fdother.NativeRNGStep(seed) ||
		binary.LittleEndian.Uint16(records[0x40:0x42]) != 100 || records[0x26] != 0 {
		t.Fatalf("failed gate result=%+v rng=%#x hp=%d marker=%d", result, nextRNG, binary.LittleEndian.Uint16(records[0x40:0x42]), records[0x26])
	}
}
