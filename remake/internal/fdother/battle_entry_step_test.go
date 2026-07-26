package fdother

import (
	"encoding/binary"
	"testing"
)

func TestNativeBattleEntryStepPreservesRawGateAndClampedAdvance(t *testing.T) {
	raw := make([]byte, 0x50)
	raw[6] = 2
	binary.LittleEndian.PutUint16(raw[0x40:], 30)
	binary.LittleEndian.PutUint16(raw[0x42:], 100)
	next, eligible, changed, err := NativeBattleEntryStep(raw)
	if err != nil || !eligible || !changed || next != 50 {
		t.Fatalf("step=%d eligible=%v changed=%v err=%v", next, eligible, changed, err)
	}
	binary.LittleEndian.PutUint16(raw[0x40:], 95)
	next, eligible, changed, err = NativeBattleEntryStep(raw)
	if err != nil || !eligible || !changed || next != 100 {
		t.Fatalf("clamp step=%d eligible=%v changed=%v err=%v", next, eligible, changed, err)
	}
}

func TestNativeBattleEntryStepRejectsOtherRawGates(t *testing.T) {
	for _, mutate := range []func([]byte){
		func(raw []byte) { raw[6] = 1 },
		func(raw []byte) { raw[5] = 1 },
		func(raw []byte) { raw[5] = 0x80 },
		func(raw []byte) { raw[0x25] = 1 },
		func(raw []byte) { raw[0x26] = 1 },
	} {
		raw := make([]byte, 0x50)
		raw[6] = 2
		binary.LittleEndian.PutUint16(raw[0x40:], 20)
		binary.LittleEndian.PutUint16(raw[0x42:], 100)
		mutate(raw)
		before := append([]byte(nil), raw...)
		if _, eligible, _, err := NativeBattleEntryStep(raw); err != nil || eligible || string(raw) != string(before) {
			t.Fatalf("gate mutation accepted: eligible=%v err=%v", eligible, err)
		}
	}
}
