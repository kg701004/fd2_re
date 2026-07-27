package battle

import (
	"encoding/binary"
	"testing"
)

func TestApplyNativeRawHPRestoreMatches1C916Core(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 10)
	binary.LittleEndian.PutUint16(records[0x42:0x44], 100)
	records[0x20], records[0x21], records[7] = 9, 2, 0
	got, err := ApplyNativeRawHPRestore(records, 0, 20, 0)
	if err != nil {
		t.Fatal(err)
	}
	if got.Rolled != 18 || got.Actual != 18 || got.Score != 230 || got.RNGState == 0 || binary.LittleEndian.Uint16(records[0x40:0x42]) != 28 {
		t.Fatalf("result=%+v hp=%d", got, binary.LittleEndian.Uint16(records[0x40:0x42]))
	}
}

func TestApplyNativeRawHPRestoreClampsAndPreflights(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 95)
	binary.LittleEndian.PutUint16(records[0x42:0x44], 100)
	before := append([]byte(nil), records...)
	got, err := ApplyNativeRawHPRestore(records, 0, 100, 0x1234)
	if err != nil || got.Actual != 5 || binary.LittleEndian.Uint16(records[0x40:0x42]) != 100 {
		t.Fatalf("result=%+v err=%v hp=%d", got, err, binary.LittleEndian.Uint16(records[0x40:0x42]))
	}
	if _, err := ApplyNativeRawHPRestore(before[:nativeRecordSize-1], 0, 1, 0); err == nil {
		t.Fatal("short record unexpectedly accepted")
	}
	if _, err := ApplyNativeRawHPRestore(records, -1, 1, 0); err == nil {
		t.Fatal("negative unit unexpectedly accepted")
	}
}

func TestApplyNativeRawMPRestoreUsesMPOffsetsAndNoClassBonus(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x44:0x46], 10)
	binary.LittleEndian.PutUint16(records[0x46:0x48], 100)
	records[0x20], records[0x21], records[7] = 9, 2, 0
	got, err := ApplyNativeRawMPRestore(records, 0, 20, 0)
	if err != nil || got.Actual != 18 || got.Score != 14 || binary.LittleEndian.Uint16(records[0x44:0x46]) != 28 {
		t.Fatalf("result=%+v mp=%d err=%v", got, binary.LittleEndian.Uint16(records[0x44:0x46]), err)
	}
}

func TestApplyNativeRawHPRestoreListMatches211A4Order(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	for unit := 0; unit < 2; unit++ {
		base := unit * nativeRecordSize
		binary.LittleEndian.PutUint16(records[base+0x40:base+0x42], uint16(10+unit))
		binary.LittleEndian.PutUint16(records[base+0x42:base+0x44], 100)
		records[base+0x20], records[base+0x21], records[base+7] = 9, byte(2+unit), 0
	}
	wantRecords := append([]byte(nil), records...)
	first, err := ApplyNativeRawHPRestore(wantRecords, 1, 20, 0)
	if err != nil {
		t.Fatal(err)
	}
	second, err := ApplyNativeRawHPRestore(wantRecords, 0, 20, first.RNGState)
	if err != nil {
		t.Fatal(err)
	}
	got, err := ApplyNativeRawHPRestoreList(records, []byte{1, 0}, 20, 0)
	if err != nil {
		t.Fatal(err)
	}
	if got.RNGState != second.RNGState || got.Score != first.Score+second.Score || len(got.Results) != 2 {
		t.Fatalf("batch=%+v first=%+v second=%+v", got, first, second)
	}
	if string(records) != string(wantRecords) {
		t.Fatal("batch mutation order differs from 0x211a4 sequential loop")
	}
}

func TestApplyNativeRawHPRestoreListPreflightsAtomically(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 10)
	binary.LittleEndian.PutUint16(records[0x42:0x44], 100)
	before := append([]byte(nil), records...)
	if _, err := ApplyNativeRawHPRestoreList(records, []byte{0, 1}, 20, 0); err == nil {
		t.Fatal("invalid later target unexpectedly accepted")
	}
	if string(records) != string(before) {
		t.Fatal("invalid target list partially mutated an earlier record")
	}
}
