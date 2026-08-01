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

func TestApplyNativeRuntimeEquipmentRecalcUsesTransientModifiers(t *testing.T) {
	record := make([]byte, nativeEquipmentRecordSize)
	binary.LittleEndian.PutUint16(record[0x37:], 20)
	binary.LittleEndian.PutUint16(record[0x39:], 0xffec)
	binary.LittleEndian.PutUint16(record[0x3e:], 7)
	record[0x22], record[0x23], record[0x24] = 1, 1, 1
	record[0x0a], record[0x0b] = nativeEquippedMask, 1
	table := make([]byte, 2*NativeItemEffectRowSize)
	row, _ := NativeItemEffectRowOffset(1)
	binary.LittleEndian.PutUint16(table[row+1:], 3)
	binary.LittleEndian.PutUint16(table[row+5:], 4)
	binary.LittleEndian.PutUint16(table[row+3:], 5)
	binary.LittleEndian.PutUint16(table[row+7:], 6)

	if err := ApplyNativeRuntimeEquipmentRecalc(record, table); err != nil {
		t.Fatal(err)
	}
	// The exact double 1.15 is slightly below the decimal value. x87 extended
	// precision plus toward-zero rounding therefore maps 23 to 26 and -16 to
	// -18 here; a host binary64 shortcut would hide this boundary behavior.
	want := [4]int16{26, -18, 27, 28}
	got := [4]int16{
		nativeSignedWord(record, 0x48), nativeSignedWord(record, 0x4a),
		nativeSignedWord(record, 0x4c), nativeSignedWord(record, 0x4e),
	}
	if got != want {
		t.Fatalf("runtime raw totals=%v want %v", got, want)
	}
}

func TestNativeScale115PreservesX87TowardZeroBoundary(t *testing.T) {
	for _, tc := range []struct {
		value int32
		want  int32
	}{
		{value: 20, want: 22},
		{value: -20, want: -22},
		{value: 100, want: 114},
		{value: -100, want: -114},
		{value: 0, want: 0},
	} {
		if got := nativeScale115TowardZero(tc.value); got != tc.want {
			t.Fatalf("native scale(%d)=%d want %d", tc.value, got, tc.want)
		}
	}
}

func TestApplyNativeRuntimeEquipmentRecalcRejectsMissingRowAtomically(t *testing.T) {
	record := make([]byte, nativeEquipmentRecordSize)
	record[0x0a], record[0x0b] = nativeEquippedMask, 0xff
	record[0x22], record[0x23], record[0x24] = 1, 1, 1
	before := append([]byte(nil), record...)
	if err := ApplyNativeRuntimeEquipmentRecalc(record, make([]byte, NativeItemEffectRowSize)); err == nil {
		t.Fatal("missing runtime item row accepted")
	}
	if string(record) != string(before) {
		t.Fatal("failed runtime recalc mutated record")
	}
}
