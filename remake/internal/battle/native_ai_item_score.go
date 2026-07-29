package battle

import (
	"encoding/binary"
	"fmt"
)

// ScoreNativeAIItemCommandTargets reproduces 0x15880 for one item row and
// its already-built target-index list. itemType is row +0x0d and itemWord is
// row +0x0e. No gameplay effect name is assigned to either field.
func ScoreNativeAIItemCommandTargets(
	records []byte,
	targets []byte,
	itemType int,
	itemWord int,
	book []NativeCommandRecord,
) (int, error) {
	if len(records)%nativeRecordSize != 0 || itemType < 0 || itemType > 0xff ||
		itemWord < 0 || itemWord > 0xffff {
		return 0, fmt.Errorf("native AI item score inputs are malformed")
	}
	count := len(records) / nativeRecordSize
	for _, index := range targets {
		if int(index) >= count {
			return 0, fmt.Errorf("native AI item score target %d is out of bounds", index)
		}
	}
	switch itemType {
	case 5, 0x0d:
		score := 0
		for _, index := range targets {
			record := records[int(index)*nativeRecordSize:]
			current := int(binary.LittleEndian.Uint16(record[0x40:0x42]))
			maximum := int(binary.LittleEndian.Uint16(record[0x42:0x44]))
			value := 0
			if current <= maximum/3 {
				value = 8
			} else if current <= maximum/2 {
				value = 3
			}
			if record[0x34]&0x80 != 0 {
				value *= 3
			}
			score += value
		}
		return score, nil
	case 0x14, 0x15, 0x18:
		threshold := itemWord
		if itemType != 0x18 {
			if itemWord >= len(book) || len(book) != NativeCommandRecordCount ||
				book[itemWord].ID != itemWord {
				return 0, fmt.Errorf("native AI item score command record is unavailable")
			}
			threshold = book[itemWord].Damage
		}
		score := 0
		for _, index := range targets {
			record := records[int(index)*nativeRecordSize:]
			current := int(binary.LittleEndian.Uint16(record[0x40:0x42]))
			if current <= threshold {
				score += 0x12
			} else {
				score += 8
			}
		}
		return score, nil
	default:
		return 0, nil
	}
}
