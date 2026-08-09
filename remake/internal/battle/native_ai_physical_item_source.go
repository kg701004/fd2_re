package battle

import "fmt"

// NativeAIPhysicalItemSource 保存 0x14237 actor 端已證實的物品來源。
// Slot／ItemID／RawGeometryByte0B／RawGeometryByte0C 都保留原始欄位角色；
// 不把兩個幾何 byte 命名成射程、範圍或陣營。
type NativeAIPhysicalItemSource struct {
	Slot              int
	ItemID            byte
	Row               []byte
	RawGeometryByte0B byte
	RawGeometryByte0C byte
}

// ResolveNativeAIPhysicalItemSource 重播 0x14288..0x142BE 的無副作用來源鏈：
//
//	0x1B83D(unit, 0) → equipped low-item slot
//	0x1B722(unit, slot) → runtime record +0x0B + slot*2
//	0x4E56C(item) → 0x602AD + item*0x17
//
// 它只回傳 detached item-row snapshot 與 0x142B2 讀取的兩個 raw byte，
// 不產生 target geometry、不評分、不移動，也不接 NextAIPlan。缺少完整
// runtime record 或 item table 時失敗即關閉；沒有符合的 equipped low item
// 則回傳 found=false，對應原版 0x1B83D 的 -1 路徑。
func ResolveNativeAIPhysicalItemSource(
	record []byte,
	itemRows []byte,
) (NativeAIPhysicalItemSource, bool, error) {
	if len(record) < nativeRecordSize {
		return NativeAIPhysicalItemSource{}, false, fmt.Errorf(
			"native AI physical item source record has %d bytes, want at least %d",
			len(record), nativeRecordSize,
		)
	}
	if len(itemRows) == 0 || len(itemRows)%NativeItemEffectRowSize != 0 ||
		len(itemRows)/NativeItemEffectRowSize > 0x100 {
		return NativeAIPhysicalItemSource{}, false, fmt.Errorf(
			"native AI physical item source table has invalid byte length %d",
			len(itemRows),
		)
	}

	flags := make([]int, nativeInventoryCells)
	slots := make([]int, nativeInventoryCells)
	for slot := 0; slot < nativeInventoryCells; slot++ {
		offset := 0x0a + slot*2
		flags[slot] = int(record[offset])
		slots[slot] = int(record[offset+1])
	}
	selected, err := NativeEquippedInventorySlot(flags, slots, 0)
	if err != nil {
		return NativeAIPhysicalItemSource{}, false, err
	}
	if selected < 0 {
		return NativeAIPhysicalItemSource{}, false, nil
	}

	itemID := byte(slots[selected])
	rowOffset, err := NativeItemEffectRowOffset(int(itemID))
	if err != nil || rowOffset+NativeItemEffectRowSize > len(itemRows) {
		if err == nil {
			err = fmt.Errorf("item row offset %#x exceeds table", rowOffset)
		}
		return NativeAIPhysicalItemSource{}, false, fmt.Errorf(
			"native AI physical item source item %#x: %w", itemID, err,
		)
	}
	row := append([]byte(nil), itemRows[rowOffset:rowOffset+NativeItemEffectRowSize]...)
	return NativeAIPhysicalItemSource{
		Slot:              selected,
		ItemID:            itemID,
		Row:               row,
		RawGeometryByte0B: row[0x0b],
		RawGeometryByte0C: row[0x0c],
	}, true, nil
}
