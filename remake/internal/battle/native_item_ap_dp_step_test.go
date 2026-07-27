package battle

import (
	"encoding/binary"
	"testing"
)

func TestNativeType15And16RetainedAPDPRoutes(t *testing.T) {
	for _, tc := range []struct {
		typ          byte
		stat         NativeItemDerivedStat
		marker, word int
		current      uint16
		want         uint16
	}{
		{15, NativeItemDerivedDP, 0x23, 0x4a, 100, 116},
		{16, NativeItemDerivedAP, 0x22, 0x48, 200, 231},
	} {
		records := make([]byte, nativeRecordSize)
		binary.LittleEndian.PutUint16(records[tc.word:], tc.current)
		route, ok := NativeItemAPDPStepRouteForType(tc.typ)
		if !ok || route.DerivedStat != tc.stat || route.ConsumesSource {
			t.Fatalf("type %#x route = %#v, %v", tc.typ, route, ok)
		}
		result, nextRNG, _, err := ApplyNativeItemAPDPStep(records, []byte{0}, route, 0)
		if err != nil {
			t.Fatal(err)
		}
		if len(result) != 1 || !result[0].Processed || nextRNG == 0 {
			t.Fatalf("type %#x result=%+v rng=%#x", tc.typ, result, nextRNG)
		}
		if got := binary.LittleEndian.Uint16(records[tc.word:]); got != tc.want {
			t.Fatalf("type %#x updated word=%d, want %d", tc.typ, got, tc.want)
		}
		if records[tc.marker] == 0 {
			t.Fatalf("type %#x marker not written", tc.typ)
		}
	}
}

func TestNativeAPDPStepMarkedTargetSkipsRNG(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x22] = 3
	binary.LittleEndian.PutUint16(records[0x48:], 100)
	route, _ := NativeItemAPDPStepRouteForType(16)
	result, nextRNG, _, err := ApplyNativeItemAPDPStep(records, []byte{0}, route, 0x1234)
	if err != nil {
		t.Fatal(err)
	}
	if result[0].Processed || nextRNG != 0x1234 || binary.LittleEndian.Uint16(records[0x48:]) != 100 {
		t.Fatalf("marked result=%+v rng=%#x word=%d", result, nextRNG, binary.LittleEndian.Uint16(records[0x48:]))
	}
}
