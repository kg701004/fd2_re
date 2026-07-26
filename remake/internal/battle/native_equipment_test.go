package battle

import (
	"encoding/binary"
	"testing"
)

func TestApplyNativeEquipmentRecalcUsesRawFlagsRowsAndWordWrap(t *testing.T) {
	record := make([]byte, nativeEquipmentRecordSize)
	binary.LittleEndian.PutUint16(record[0x37:], uint16(int16(10)))
	binary.LittleEndian.PutUint16(record[0x39:], 0xfffe)
	binary.LittleEndian.PutUint16(record[0x3e:], uint16(int16(7)))
	// slot 0 selected, slot 1 has an item but no equipped bit, slot 2 selected.
	record[0x0a], record[0x0b] = nativeEquippedMask, 1
	record[0x0c], record[0x0d] = 0, 2
	record[0x0e], record[0x0f] = nativeEquippedMask, 2
	table := make([]byte, 0x100*NativeItemEffectRowSize)
	set := func(item, field, value int16) {
		row, _ := NativeItemEffectRowOffset(int(item))
		binary.LittleEndian.PutUint16(table[row+int(field):], uint16(value))
	}
	set(1, 1, 5)
	set(1, 5, -3)
	set(1, 3, 2)
	set(1, 7, 1)
	set(2, 1, 0x7fff)
	set(2, 5, 1)
	set(2, 3, -2)
	set(2, 7, 4)
	if err := ApplyNativeEquipmentRecalc(record, table); err != nil {
		t.Fatal(err)
	}
	got := [4]int16{nativeSignedWord(record, 0x48), nativeSignedWord(record, 0x4a), nativeSignedWord(record, 0x4c), nativeSignedWord(record, 0x4e)}
	wantAP := int16(0x7fff)
	wantAP += 15
	want := [4]int16{wantAP, -4, 7, 12}
	if got != want {
		t.Fatalf("raw totals=%v want %v", got, want)
	}
}

func TestApplyNativeEquipmentRecalcRejectsMissingRowAtomically(t *testing.T) {
	record := make([]byte, nativeEquipmentRecordSize)
	record[0x0a], record[0x0b] = nativeEquippedMask, 0xff
	before := append([]byte(nil), record...)
	if err := ApplyNativeEquipmentRecalc(record, make([]byte, NativeItemEffectRowSize)); err == nil {
		t.Fatal("missing item row accepted")
	}
	if string(record) != string(before) {
		t.Fatal("failed raw recalc mutated record")
	}
}

func TestApplyNativeEquipmentRecalcIgnoresUnequippedItems(t *testing.T) {
	record := make([]byte, nativeEquipmentRecordSize)
	record[0x0b] = 0xff // no flag bit: table need not contain item 0xff row
	if err := ApplyNativeEquipmentRecalc(record, make([]byte, NativeItemEffectRowSize)); err != nil {
		t.Fatal(err)
	}
	if nativeSignedWord(record, 0x48) != 0 || nativeSignedWord(record, 0x4a) != 0 {
		t.Fatal("unequipped item changed raw totals")
	}
}
