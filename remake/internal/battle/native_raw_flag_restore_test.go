package battle

import (
	"encoding/binary"
	"testing"
)

func TestApplyNativeRawFlagRestoreMatches22AF6(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	for i := 0; i < 2; i++ {
		base := i * nativeRecordSize
		binary.LittleEndian.PutUint16(records[base+0x40:base+0x42], 10)
		binary.LittleEndian.PutUint16(records[base+0x42:base+0x44], 100)
		records[base+0x20], records[base+0x21] = 9, 2
	}
	records[0x25] = 1
	got, state, score, err := ApplyNativeRawFlagRestore(records, []byte{0, 1}, 0x25, 0)
	if err != nil || len(got) != 2 || !got[0].Applied || got[1].Applied || state == 0 || score != 128 || records[0x25] != 0 || records[nativeRecordSize+0x25] != 0 || binary.LittleEndian.Uint16(records[0x40:0x42]) != 19 {
		t.Fatalf("results=%+v state=%#x score=%d marker=%#x hp=%d err=%v", got, state, score, records[0x25], binary.LittleEndian.Uint16(records[0x40:0x42]), err)
	}
}

func TestApplyNativeRawFlagRestorePreflights(t *testing.T) {
	if _, _, _, err := ApplyNativeRawFlagRestore(make([]byte, nativeRecordSize), []byte{0}, nativeRecordSize, 0); err == nil {
		t.Fatal("invalid marker offset unexpectedly accepted")
	}
	if _, _, _, err := ApplyNativeRawFlagRestore(make([]byte, nativeRecordSize), []byte{1}, 0x25, 0); err == nil {
		t.Fatal("out-of-range target unexpectedly accepted")
	}
}
