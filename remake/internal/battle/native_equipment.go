package battle

import (
	"encoding/binary"
	"fmt"
)

const (
	nativeEquipmentRecordSize = 0x50
	nativeInventoryOffset     = 0x0a
	nativeInventoryCells      = 8
	nativeEquippedMask        = 0x40
)

func nativeSignedWord(buf []byte, off int) int16 {
	return int16(binary.LittleEndian.Uint16(buf[off : off+2]))
}

func nativePutWord(buf []byte, off int, value int16) {
	binary.LittleEndian.PutUint16(buf[off:off+2], uint16(value))
}

// ApplyNativeEquipmentRecalc reproduces the proven arithmetic tail of
// 0x1145a. record is one native 0x50-byte persistent record; itemTable starts
// at the relocated 0x602ad row table. The eight inventory cells are raw
// [flag,item] pairs at +0x0a. Only flag bit 0x40 selects a row. Cross-checking
// all 215 known raw rows against item.json identifies row +1/+3/+5/+7 as the
// AP/HIT/DP/EV equipment words. Native accumulation order is AP/DP/HIT/EV into
// record +0x48/+0x4a/+0x4c/+0x4e. All word writes wrap at 16 bits.
//
// The operation is fail-closed and atomic: malformed record/table input is
// rejected before any destination byte is changed.
func ApplyNativeEquipmentRecalc(record, itemTable []byte) error {
	if len(record) < nativeEquipmentRecordSize {
		return fmt.Errorf("native equipment: record=%d, want at least %#x", len(record), nativeEquipmentRecordSize)
	}
	if len(itemTable) == 0 {
		return fmt.Errorf("native equipment: empty item table")
	}
	items := make([]int, nativeInventoryCells)
	for slot := 0; slot < nativeInventoryCells; slot++ {
		cell := nativeInventoryOffset + slot*2
		if record[cell]&nativeEquippedMask == 0 {
			continue
		}
		item := int(record[cell+1])
		row, err := NativeItemEffectRowOffset(item)
		if err != nil || row+8 > len(itemTable) {
			return fmt.Errorf("native equipment: item %#x row unavailable", item)
		}
		items[slot] = item + 1 // zero means unselected; item 0 is represented by 1
	}
	baseAP := int(nativeSignedWord(record, 0x37))
	baseDP := int(nativeSignedWord(record, 0x39))
	baseDX := int(nativeSignedWord(record, 0x3e))
	totals := [4]int{baseAP, baseDP, baseDX, baseDX}
	for slot, marker := range items {
		if marker == 0 {
			continue
		}
		row, _ := NativeItemEffectRowOffset(marker - 1)
		// The native row accesses are non-contiguous in this order.
		for i, field := range [...]int{1, 5, 3, 7} {
			totals[i] += int(nativeSignedWord(itemTable, row+field))
		}
		_ = slot
	}
	for i, off := range [...]int{0x48, 0x4a, 0x4c, 0x4e} {
		nativePutWord(record, off, int16(totals[i]))
	}
	return nil
}
