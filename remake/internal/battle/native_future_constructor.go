package battle

import (
	"encoding/binary"
	"fmt"
)

// NativeFutureConstructorBase is the table-derived subset written by
// 0x10d7f..0x10ebd before inventory/equipment recomputation. Values retain
// the original 16-bit write boundary.
type NativeFutureConstructorBase struct {
	RecordRace  byte
	RecordClass byte
	BaseAP      uint16
	BaseDP      uint16
	BaseDX      uint16
	Mobility    byte
	MaxHP       uint16
	MaxMP       uint16
}

// DecodeNativeFutureConstructorBase transcribes the two b1-selected table
// branches in 0x10d99..0x10ebd. It deliberately stops before 0x1b750:
// effective AP/DP/HIT/EV require the separately verified inventory table and
// are not inferred here.
func DecodeNativeFutureConstructorBase(
	table *NativeConstructorTable,
	level byte,
) (NativeFutureConstructorBase, error) {
	if err := table.validate(); err != nil {
		return NativeFutureConstructorBase{}, err
	}
	if table == nil {
		return NativeFutureConstructorBase{}, fmt.Errorf(
			"native future constructor table unavailable",
		)
	}

	record := table.Record
	if table.Branch == "high_class" {
		return NativeFutureConstructorBase{
			RecordRace:  record[0],
			RecordClass: record[1],
			BaseAP:      mulWord(record[5], level),
			BaseDP:      mulWord(record[6], level),
			BaseDX:      mulWord(record[7], level),
			Mobility:    record[8],
			MaxHP:       uint16(uint32(binary.LittleEndian.Uint16(record[2:4])) * uint32(level)),
			MaxMP:       mulWord(record[4], level),
		}, nil
	}

	aux := table.AuxRecord
	levelMinusOne := int32(level) - 1
	return NativeFutureConstructorBase{
		RecordRace:  record[0],
		RecordClass: record[1],
		BaseAP: addScaledWord(
			binary.LittleEndian.Uint16(record[0x12:0x14]),
			aux[0], int32(level),
		),
		BaseDP: addScaledWord(
			binary.LittleEndian.Uint16(record[0x14:0x16]),
			aux[2], int32(level),
		),
		BaseDX: addScaledWord(
			binary.LittleEndian.Uint16(record[0x16:0x18]),
			aux[4], int32(level),
		),
		Mobility: record[7],
		MaxHP: addScaledWord(
			binary.LittleEndian.Uint16(record[3:5]),
			aux[6], levelMinusOne,
		),
		MaxMP: addScaledWord(
			binary.LittleEndian.Uint16(record[5:7]),
			aux[8], levelMinusOne,
		),
	}, nil
}

func mulWord(value, multiplier byte) uint16 {
	return uint16(uint32(value) * uint32(multiplier))
}

func addScaledWord(base uint16, value byte, multiplier int32) uint16 {
	return uint16(int32(base) + int32(value)*multiplier)
}
