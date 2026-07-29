package battle

import (
	"encoding/binary"
	"testing"
)

func TestNativeItemPanelRecordForUnitUsesProvenRawSelectors(t *testing.T) {
	unit := &Unit{
		BattleFig: 9, NativeIdentity: 4, HasNativeIdentity: true,
		NativeRecordByte8: 0x60, HasNativeRecordByte8: true,
		NativeRecordByte6: 1, HasNativeRecordByte6: true,
		NativeRecordRace: 7, HasNativeRecordRace: true,
		NativeRecordClass: 8, HasNativeRecordClass: true,
		Lv: 12, MV: 5, Exp: 34, DX: 56,
		HP: 80, MaxHP: 100, MP: 20, MaxMP: 40,
		AP: 123, DP: 98, HIT: 76, EV: 54,
		InventorySlots:       []int{0, 79, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0x40, 0, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
		NativeTransient:      [6]byte{1, 2, 3, 4, 5, 6},
	}
	record, err := NativeItemPanelRecordForUnit(unit)
	if err != nil {
		t.Fatal(err)
	}
	if len(record) != 80 || record[6] != 1 || record[7] != 9 || record[8] != 0x60 ||
		record[0x0a] != 0x40 || record[0x0b] != 0 || record[0x0d] != 79 ||
		record[0x1f] != 7 || record[0x20] != 8 || record[0x21] != 12 ||
		record[0x22] != 1 || record[0x27] != 6 || record[0x3b] != 5 ||
		record[0x3c] != 34 {
		t.Fatalf("record bytes=%v", record)
	}
	for offset, want := range map[int]uint16{
		0x3e: 56, 0x40: 80, 0x42: 100, 0x44: 20, 0x46: 40,
		0x48: 123, 0x4a: 98, 0x4c: 76, 0x4e: 54,
	} {
		if got := binary.LittleEndian.Uint16(record[offset:]); got != want {
			t.Fatalf("record[%#x]=%d, want %d", offset, got, want)
		}
	}
}

func TestNativeItemPanelRecordForUnitRejectsMissingRawProvenance(t *testing.T) {
	if record, err := NativeItemPanelRecordForUnit(&Unit{
		BattleFig: 1, NativeIdentity: 2, HasNativeIdentity: true,
		Lv: 1, InventorySlots: make([]int, 8), NativeInventoryFlags: make([]int, 8),
	}); err == nil || record != nil {
		t.Fatalf("record=%v err=%v", record, err)
	}
	unit := &Unit{
		BattleFig: 1, NativeIdentity: 2, HasNativeIdentity: true,
		NativeRecordByte6: 1, HasNativeRecordByte6: true,
		NativeRecordRace: 1, HasNativeRecordRace: true,
		NativeRecordClass: 2, HasNativeRecordClass: true,
		Lv: 1, Exp: 1.5,
		InventorySlots: make([]int, 8), NativeInventoryFlags: make([]int, 8),
	}
	if record, err := NativeItemPanelRecordForUnit(unit); err == nil || record != nil {
		t.Fatalf("fractional EXP record=%v err=%v", record, err)
	}
}
