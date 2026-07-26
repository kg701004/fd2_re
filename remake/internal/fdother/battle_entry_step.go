package fdother

import (
	"encoding/binary"
	"errors"
)

// NativeBattleEntryStep applies the proven 0x1a30b raw record gate and
// word+0x40 toward word+0x42 transition. Field offsets remain unnamed.
func NativeBattleEntryStep(raw []byte) (next uint16, eligible, changed bool, err error) {
	if len(raw) < 0x44 {
		return 0, false, false, errors.New("fdother: battle-entry record is shorter than 0x44 bytes")
	}
	if raw[6] != 2 || raw[5]&0x81 != 0 || raw[0x25] != 0 || raw[0x26] != 0 {
		return binary.LittleEndian.Uint16(raw[0x40:]), false, false, nil
	}
	current := binary.LittleEndian.Uint16(raw[0x40:])
	maximum := binary.LittleEndian.Uint16(raw[0x42:])
	if current == maximum {
		return current, false, false, nil
	}
	step := maximum / 5
	next = current + step
	if next > maximum {
		next = maximum
	}
	binary.LittleEndian.PutUint16(raw[0x40:], next)
	return next, true, next != current, nil
}
