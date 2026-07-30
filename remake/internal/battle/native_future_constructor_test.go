package battle

import (
	"path/filepath"
	"testing"
)

func TestDecodeNativeFutureConstructorBaseHighClass(t *testing.T) {
	got, err := DecodeNativeFutureConstructorBase(&NativeConstructorTable{
		Branch: "high_class",
		Index:  0,
		Record: []byte{4, 5, 0x34, 0x12, 6, 7, 8, 9, 10, 0},
	}, 3)
	if err != nil {
		t.Fatal(err)
	}
	want := NativeFutureConstructorBase{
		RecordRace: 4, RecordClass: 5,
		BaseAP: 21, BaseDP: 24, BaseDX: 27, Mobility: 10,
		MaxHP: 0x369c, MaxMP: 18,
	}
	if got != want {
		t.Fatalf("high constructor=%#v want %#v", got, want)
	}
}

func TestDecodeNativeFutureConstructorBaseLowerClass(t *testing.T) {
	record := make([]byte, 24)
	record[0], record[1], record[7] = 1, 2, 9
	record[3], record[4] = 100, 0
	record[5], record[6] = 20, 0
	record[0x12], record[0x14], record[0x16] = 10, 11, 12
	aux := []byte{2, 0, 3, 0, 4, 0, 5, 0, 6, 0, 0}
	got, err := DecodeNativeFutureConstructorBase(&NativeConstructorTable{
		Branch: "lower_class", Index: 0, Record: record, AuxRecord: aux,
	}, 4)
	if err != nil {
		t.Fatal(err)
	}
	want := NativeFutureConstructorBase{
		RecordRace: 1, RecordClass: 2,
		BaseAP: 18, BaseDP: 23, BaseDX: 28, Mobility: 9,
		MaxHP: 115, MaxMP: 38,
	}
	if got != want {
		t.Fatalf("lower constructor=%#v want %#v", got, want)
	}
}

func TestDecodeNativeFutureConstructorBasePreservesLevelZeroWrap(t *testing.T) {
	record := make([]byte, 24)
	record[3], record[5] = 4, 3
	aux := []byte{0, 0, 0, 0, 0, 0, 5, 0, 6, 0, 0}
	got, err := DecodeNativeFutureConstructorBase(&NativeConstructorTable{
		Branch: "lower_class", Index: 0, Record: record, AuxRecord: aux,
	}, 0)
	if err != nil {
		t.Fatal(err)
	}
	if got.MaxHP != 0xffff || got.MaxMP != 0xfffd {
		t.Fatalf("level-zero wrap HP/MP=%#x/%#x", got.MaxHP, got.MaxMP)
	}
}

func TestAllMapUnitsMatchNativeFutureConstructorProjection(t *testing.T) {
	matches := 0
	for mapIndex := 0; mapIndex < 33; mapIndex++ {
		path := filepath.Join(
			"../../assets/maps",
			"map"+itoa(mapIndex),
			"map"+itoa(mapIndex)+"_units.json",
		)
		st, err := Load(path)
		if err != nil {
			t.Fatalf("map%d load: %v", mapIndex, err)
		}
		for unitIndex, unit := range st.Units {
			if unit.NativeConstructor == nil {
				continue
			}
			got, err := DecodeNativeFutureConstructorBase(
				unit.NativeConstructor, byte(unit.Lv),
			)
			if err != nil {
				t.Fatalf("map%d unit%d constructor: %v", mapIndex, unitIndex, err)
			}
			if !unit.HasNativeRecordRace || unit.NativeRecordRace != got.RecordRace ||
				!unit.HasNativeRecordClass || unit.NativeRecordClass != got.RecordClass ||
				!unit.HasNativeRecordWord42 || unit.NativeRecordWord42 != got.MaxHP ||
				!unit.HasNativeRecordWord46 || unit.NativeRecordWord46 != got.MaxMP {
				t.Fatalf(
					"map%d unit%d projection race/class/HP/MP=%d/%d/%d/%d want %d/%d/%d/%d",
					mapIndex, unitIndex,
					unit.NativeRecordRace, unit.NativeRecordClass,
					unit.NativeRecordWord42, unit.NativeRecordWord46,
					got.RecordRace, got.RecordClass, got.MaxHP, got.MaxMP,
				)
			}
			matches++
		}
	}
	if matches == 0 {
		t.Fatal("no map unit carried native constructor provenance")
	}
}

func itoa(value int) string {
	if value == 0 {
		return "0"
	}
	var digits [20]byte
	index := len(digits)
	for value > 0 {
		index--
		digits[index] = byte('0' + value%10)
		value /= 10
	}
	return string(digits[index:])
}
