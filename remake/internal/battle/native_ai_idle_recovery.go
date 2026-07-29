package battle

import (
	"encoding/binary"
	"fmt"
)

// ApplyNativeAIIdleRecovery 保存 0x13fd4 的 gameplay mutation：
// current HP 與 max HP 不同且 raw +0x25/+0x26 皆為零時，current HP
// 增加 max HP/5，再以 max HP 為上限。畫面呈現不屬於此 state-only slice。
func ApplyNativeAIIdleRecovery(records []byte, count, unit int) (bool, error) {
	if count < 0 || count > len(records)/nativeRecordSize || unit < 0 || unit >= count {
		return false, fmt.Errorf("native AI idle recovery unit is out of bounds")
	}
	record := records[unit*nativeRecordSize : (unit+1)*nativeRecordSize]
	current := binary.LittleEndian.Uint16(record[0x40:0x42])
	maximum := binary.LittleEndian.Uint16(record[0x42:0x44])
	if current == maximum || record[0x25] != 0 || record[0x26] != 0 {
		return false, nil
	}
	next := uint32(current) + uint32(maximum)/5
	if next > uint32(maximum) {
		next = uint32(maximum)
	}
	binary.LittleEndian.PutUint16(record[0x40:0x42], uint16(next))
	return true, nil
}
