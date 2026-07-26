package battle

import (
	"encoding/binary"
	"testing"
)

func TestApplyNativeRawHPDamageMatches1C81FCore(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 20)
	got, err := ApplyNativeRawHPDamage(records, 0, 10, 0)
	if err != nil || got.Rolled != 9 || got.Actual != 9 || got.RNGState == 0 || binary.LittleEndian.Uint16(records[0x40:0x42]) != 11 {
		t.Fatalf("result=%+v hp=%d err=%v", got, binary.LittleEndian.Uint16(records[0x40:0x42]), err)
	}
}

func TestApplyNativeRawHPDamageClampsAndPreflights(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	if _, err := ApplyNativeRawHPDamage(records, 0, 10, 0); err != nil {
		t.Fatal(err)
	}
	if binary.LittleEndian.Uint16(records[0x40:0x42]) != 0 {
		t.Fatal("damage did not clamp at zero")
	}
	if _, err := ApplyNativeRawHPDamage(records[:nativeRecordSize-1], 0, 1, 0); err == nil {
		t.Fatal("short record unexpectedly accepted")
	}
}
