package battle

import "fmt"

type NativeItemSelectorResult int

const (
	NativeItemSelectorWait NativeItemSelectorResult = iota
	NativeItemSelectorConfirm
	NativeItemSelectorCancel
)

// AdvanceNativeItemSelector reproduces 0x1b9de's two-column/four-row input
// state. Up/down walk the compact occupied prefix linearly with wrap; left and
// right move by four. Battle-use confirmation rejects effect type zero.
func AdvanceNativeItemSelector(
	selection, occupiedCount, scanCode int,
	battleUse bool,
	selectedEffectType byte,
) (int, NativeItemSelectorResult, error) {
	if occupiedCount <= 0 || occupiedCount > 8 || selection < 0 || selection >= occupiedCount {
		return selection, NativeItemSelectorWait, fmt.Errorf(
			"native item selector selection/count=%d/%d is invalid", selection, occupiedCount,
		)
	}
	switch scanCode {
	case 72:
		if selection == 0 {
			return occupiedCount - 1, NativeItemSelectorWait, nil
		}
		return selection - 1, NativeItemSelectorWait, nil
	case 80:
		if selection == occupiedCount-1 {
			return 0, NativeItemSelectorWait, nil
		}
		return selection + 1, NativeItemSelectorWait, nil
	case 75:
		if selection >= 4 {
			return selection - 4, NativeItemSelectorWait, nil
		}
	case 77:
		if selection <= 3 && selection+4 < occupiedCount {
			return selection + 4, NativeItemSelectorWait, nil
		}
	case 28, 57:
		if !battleUse || selectedEffectType != 0 {
			return selection, NativeItemSelectorConfirm, nil
		}
	case 1:
		return selection, NativeItemSelectorCancel, nil
	}
	return selection, NativeItemSelectorWait, nil
}

type NativeItemSelectorCell struct {
	RawSlot      int
	DisplayIndex int
	ItemID       byte
	Equipped     bool
	Selected     bool
	LabelX       int
	LabelY       int
	CategoryIcon int
	StatIcon     int
	StatValue    int
	HasStatValue bool
}

// NativeItemSelectorCells reproduces 0x184c0's compact display and geometry.
// Empty/reserved raw slots are skipped; native writers maintain an occupied
// prefix, but keeping RawSlot explicit exposes malformed/editable holes.
func NativeItemSelectorCells(
	records []byte,
	unitIndex, selectedRawSlot int,
	effectRows []byte,
) ([]NativeItemSelectorCell, error) {
	base := unitIndex * nativeRecordSize
	if unitIndex < 0 || base < 0 || base+nativeRecordSize > len(records) {
		return nil, recordBoundsError(unitIndex)
	}
	if selectedRawSlot < -1 || selectedRawSlot >= 8 {
		return nil, fmt.Errorf("native item selector raw slot=%d is invalid", selectedRawSlot)
	}
	record := records[base : base+nativeRecordSize]
	cells := make([]NativeItemSelectorCell, 0, 8)
	for rawSlot := 0; rawSlot < 8; rawSlot++ {
		flag := record[0x0a+rawSlot*2]
		if flag&0x80 != 0 {
			continue
		}
		itemID := record[0x0b+rawSlot*2]
		rowBase := int(itemID) * NativeItemEffectRowSize
		if rowBase < 0 || rowBase+NativeItemEffectRowSize > len(effectRows) {
			return nil, fmt.Errorf("native item selector row %d is unavailable", itemID)
		}
		row := effectRows[rowBase : rowBase+NativeItemEffectRowSize]
		display := len(cells)
		cell := NativeItemSelectorCell{
			RawSlot: rawSlot, DisplayIndex: display, ItemID: itemID,
			Equipped: flag&0x40 != 0, Selected: rawSlot == selectedRawSlot,
			LabelX: 42 + 150*(display/4), LabelY: 103 + 22*(display%4),
		}
		switch {
		case row[0] < 0x15:
			cell.CategoryIcon = 59
			cell.StatIcon = 64
			cell.StatValue = int(int16(uint16(row[1]) | uint16(row[2])<<8))
			cell.HasStatValue = true
		case row[0] < 0x20:
			cell.CategoryIcon = 60
			cell.StatIcon = 65
			cell.StatValue = int(int16(uint16(row[5]) | uint16(row[6])<<8))
			cell.HasStatValue = true
		default:
			cell.CategoryIcon = 61
			switch {
			case row[0] == 0x20 && row[0x0d] == 5:
				cell.StatIcon = 66
			case row[0] == 0x20 && row[0x0d] == 11:
				cell.StatIcon = 67
			default:
				cell.StatIcon = 41
			}
			if cell.StatIcon == 66 || cell.StatIcon == 67 {
				cell.StatValue = int(int16(uint16(row[0x0e]) | uint16(row[0x0f])<<8))
				cell.HasStatValue = true
			}
		}
		if cell.Equipped {
			cell.CategoryIcon += 3
		}
		cells = append(cells, cell)
	}
	return cells, nil
}
