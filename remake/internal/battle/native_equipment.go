package battle

import (
	"encoding/binary"
	"fmt"
	"math/bits"
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

const (
	// FD2.EXE 0x5018d stores the IEEE-754 double 1.15 exactly as
	// 2589569785738035 / 2251799813685248. 0x1b750 multiplies in x87 extended
	// precision and 0x377a4 rounds toward zero, so a host binary64 multiply is
	// not interchangeable (for example, native maps 20 to 22, not 23).
	nativeScale115Numerator   = uint64(2589569785738035)
	nativeScale115Denominator = uint64(2251799813685248)
)

func nativeScale115TowardZero(value int32) int32 {
	negative := value < 0
	magnitude := uint64(value)
	if negative {
		magnitude = uint64(-int64(value))
	}
	high, low := bits.Mul64(magnitude, nativeScale115Numerator)
	quotient, _ := bits.Div64(high, low, nativeScale115Denominator)
	if negative {
		return -int32(quotient)
	}
	return int32(quotient)
}

func nativeEquipmentTotals(record, itemTable []byte, runtimeModifiers bool) ([4]int32, error) {
	if len(record) < nativeEquipmentRecordSize {
		return [4]int32{}, fmt.Errorf("native equipment: record=%d, want at least %#x", len(record), nativeEquipmentRecordSize)
	}
	if len(itemTable) == 0 {
		return [4]int32{}, fmt.Errorf("native equipment: empty item table")
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
			return [4]int32{}, fmt.Errorf("native equipment: item %#x row unavailable", item)
		}
		items[slot] = item + 1 // zero means unselected; item 0 is represented by 1
	}
	baseDX := int32(nativeSignedWord(record, 0x3e))
	totals := [4]int32{
		int32(nativeSignedWord(record, 0x37)),
		int32(nativeSignedWord(record, 0x39)),
		baseDX,
		baseDX,
	}
	if runtimeModifiers && record[0x24] != 0 {
		totals[2] += 15
		totals[3] += 15
	}
	for _, marker := range items {
		if marker == 0 {
			continue
		}
		row, _ := NativeItemEffectRowOffset(marker - 1)
		// The native row accesses are non-contiguous in this order.
		for i, field := range [...]int{1, 5, 3, 7} {
			totals[i] += int32(nativeSignedWord(itemTable, row+field))
		}
	}
	if runtimeModifiers && record[0x22] != 0 {
		totals[0] = nativeScale115TowardZero(totals[0])
	}
	if runtimeModifiers && record[0x23] != 0 {
		totals[1] = nativeScale115TowardZero(totals[1])
	}
	return totals, nil
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
	totals, err := nativeEquipmentTotals(record, itemTable, false)
	if err != nil {
		return err
	}
	for i, off := range [...]int{0x48, 0x4a, 0x4c, 0x4e} {
		nativePutWord(record, off, int16(totals[i]))
	}
	return nil
}

// ApplyNativeRuntimeEquipmentRecalc reproduces 0x1b750 for one 0x50-byte
// runtime record rooted at [0x53a45]. It differs from persistent 0x1145a:
// +0x22/+0x23 apply the exact x87 1.15 toward-zero transform to AP/DP, while
// +0x24 adds 15 to both HIT/EV bases before equipped item words are added.
// The operation validates every selected item row before changing the record.
func ApplyNativeRuntimeEquipmentRecalc(record, itemTable []byte) error {
	totals, err := nativeEquipmentTotals(record, itemTable, true)
	if err != nil {
		return err
	}
	for i, off := range [...]int{0x48, 0x4a, 0x4c, 0x4e} {
		nativePutWord(record, off, int16(totals[i]))
	}
	return nil
}
