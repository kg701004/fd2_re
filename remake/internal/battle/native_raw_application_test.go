package battle

import (
	"encoding/binary"
	"testing"
)

func TestApplyNativeRawApplicationMatches22D1B(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 20)
	records[0x20], records[0x21], records[0x25] = 1, 3, 0
	got, state, score, err := ApplyNativeRawApplication(records, []byte{0}, 0x25, 0)
	if err != nil || len(got) != 1 || !got[0].Applied || got[0].Marker < 2 || got[0].Marker > 5 || score != 24 || state == 0 || binary.LittleEndian.Uint16(records[0x40:0x42]) != 11 {
		t.Fatalf("results=%+v state=%#x score=%d marker=%d hp=%d err=%v", got, state, score, got[0].Marker, binary.LittleEndian.Uint16(records[0x40:0x42]), err)
	}
}

func TestApplyNativeRawApplicationSkipsGates(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[0x20], records[nativeRecordSize+0x20] = 0x19, 1
	records[0x25], records[nativeRecordSize+0x25] = 1, 1
	got, _, score, err := ApplyNativeRawApplication(records, []byte{0, 1}, 0x25, 0)
	if err != nil || len(got) != 2 || got[0].Applied || got[1].Applied || score != 0 {
		t.Fatalf("results=%+v score=%d err=%v", got, score, err)
	}
}
