package battle

import (
	"encoding/binary"
	"testing"
)

func TestApplyNativeWordDeltaAndRemoveUsesRawWordWrapAndRemoval(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x20:0x22], 0xfffe)
	for slot := 0; slot < 8; slot++ {
		off := nativeRecordSize + 0x0a + slot*2
		records[off], records[off+1] = byte(slot), byte(0xc0+slot)
	}
	got, err := ApplyNativeWordDeltaAndRemove(records, 0, 0x20, 3, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if got != 1 || binary.LittleEndian.Uint16(records[0x20:0x22]) != 1 {
		t.Fatalf("word=%#x result=%#x", binary.LittleEndian.Uint16(records[0x20:0x22]), got)
	}
	if records[nativeRecordSize+0x0c] != 2 || records[nativeRecordSize+0x18] != 0x80 {
		t.Fatalf("removed inventory not compacted: %#x %#x", records[nativeRecordSize+0x0c], records[nativeRecordSize+0x18])
	}
}

func TestApplyNativeWordDeltaAndRemoveRejectsBeforeMutation(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x20:0x22], 9)
	if _, err := ApplyNativeWordDeltaAndRemove(records, 0, nativeRecordSize, 1, 0, 0); err == nil {
		t.Fatal("expected invalid word offset")
	}
	if binary.LittleEndian.Uint16(records[0x20:0x22]) != 9 {
		t.Fatal("invalid input mutated word")
	}
	if _, err := ApplyNativeWordDeltaAndRemove(records, 0, 0x20, 1, 1, 0); err == nil {
		t.Fatal("expected invalid removal unit")
	}
}
