package battle

import (
	"encoding/binary"
	"testing"
)

func TestApplyNativeRawWordSubtractWrapsLow16(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x44:0x46], 2)
	got, err := ApplyNativeRawWordSubtract(records, 0, 0x44, 5)
	if err != nil || got != 0xfffd || binary.LittleEndian.Uint16(records[0x44:0x46]) != 0xfffd {
		t.Fatalf("got=%#x err=%v raw=%#x", got, err, binary.LittleEndian.Uint16(records[0x44:0x46]))
	}
}

func TestApplyNativeRawWordSubtractPreflights(t *testing.T) {
	for _, tc := range []struct {
		name      string
		records   []byte
		unit, off int
		amount    int
	}{
		{"unit", make([]byte, nativeRecordSize), -1, 0x44, 1},
		{"offset", make([]byte, nativeRecordSize), 0, nativeRecordSize, 1},
		{"amount", make([]byte, nativeRecordSize), 0, 0x44, 0x100},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if _, err := ApplyNativeRawWordSubtract(tc.records, tc.unit, tc.off, tc.amount); err == nil {
				t.Fatal("invalid raw subtract unexpectedly accepted")
			}
		})
	}
}
