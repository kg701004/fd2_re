package fdother

import (
	"encoding/binary"
	"testing"
)

func TestNativePreparationRecordGatesRemainRaw(t *testing.T) {
	raw := make([]byte, 0x50)
	raw[0x25], raw[5], raw[6], raw[7] = 1, 0, 7, 3
	binary.LittleEndian.PutUint16(raw[0x40:], 12)
	binary.LittleEndian.PutUint16(raw[0x42:], 25)
	record, err := ParseNativePreparationRecord(raw)
	if err != nil {
		t.Fatal(err)
	}
	if !NativePreparationEligible(record, 7) || NativePreparationEligible(record, 8) {
		t.Fatalf("selector gates unexpectedly changed: %#v", record)
	}
	adjusted, divisor := NativePreparationAdjustedWord40(record)
	if adjusted != 10 || divisor != 2 {
		t.Fatalf("adjusted=%d divisor=%d, want 10/2", adjusted, divisor)
	}
	record.Raw25 = 0
	if NativePreparationEligible(record, 7) {
		t.Fatal("raw +0x25 zero must reject")
	}
	record.Raw25, record.Raw5 = 1, 1
	if NativePreparationEligible(record, 7) {
		t.Fatal("raw +5 bit0 must reject")
	}
}

func TestNativePreparationAdjustedWord40Clamps(t *testing.T) {
	record := NativePreparationRecord{Word40: 3, Word42: 99}
	adjusted, divisor := NativePreparationAdjustedWord40(record)
	if adjusted != 0 || divisor != 9 {
		t.Fatalf("adjusted=%d divisor=%d, want 0/9", adjusted, divisor)
	}
}
