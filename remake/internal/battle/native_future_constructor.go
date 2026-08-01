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

// MaterializeNativeFutureConstructor applies the typed fields closed by
// 0x10c50's table/inventory tail and its 0x1b750 call. It is intentionally a
// Unit projection rather than a claim of byte-identical 0x50-byte storage:
// fields without a typed consumer remain in their existing raw provenance.
// Every source and selected item row is validated before unit is replaced.
func MaterializeNativeFutureConstructor(unit *Unit, itemTable []byte) error {
	if unit == nil || unit.NativeConstructor == nil {
		return fmt.Errorf("native future constructor provenance unavailable")
	}
	if unit.Lv < 0 || unit.Lv > 0xff {
		return fmt.Errorf("native future constructor level %d outside byte", unit.Lv)
	}
	if !unit.HasNativeRecordByte6 || unit.NativeRecordByte6 > 2 {
		return fmt.Errorf("native future constructor raw camp unavailable")
	}
	if err := ValidateNativeInventoryProjection(unit); err != nil {
		return fmt.Errorf("native future constructor inventory: %w", err)
	}
	base, err := DecodeNativeFutureConstructorBase(unit.NativeConstructor, byte(unit.Lv))
	if err != nil {
		return err
	}
	records, err := NativeInventoryRecords([]*Unit{unit}, 1)
	if err != nil {
		return err
	}
	record := records[:nativeEquipmentRecordSize]
	nativePutWord(record, 0x37, int16(base.BaseAP))
	nativePutWord(record, 0x39, int16(base.BaseDP))
	nativePutWord(record, 0x3e, int16(base.BaseDX))
	// 0x10f6b clears +0x22..+0x27 before 0x11003 calls 0x1b750.
	if err := ApplyNativeRuntimeEquipmentRecalc(record, itemTable); err != nil {
		return err
	}

	staged := *unit
	staged.NativeRecordRace, staged.HasNativeRecordRace = base.RecordRace, true
	staged.NativeRecordClass, staged.HasNativeRecordClass = base.RecordClass, true
	staged.NativeRecordByte5, staged.HasNativeRecordByte5 = 0, true
	staged.NativeTransient = [6]byte{}
	staged.BaseAP = int(int16(base.BaseAP))
	staged.BaseDP = int(int16(base.BaseDP))
	staged.BaseHIT = int(int16(base.BaseDX))
	staged.BaseEV = int(int16(base.BaseDX))
	staged.BaseMV = int(base.Mobility)
	staged.EquipmentBaseSet = true
	staged.AP = int(nativeSignedWord(record, 0x48))
	staged.DP = int(nativeSignedWord(record, 0x4a))
	staged.HIT = int(nativeSignedWord(record, 0x4c))
	staged.EV = int(nativeSignedWord(record, 0x4e))
	staged.DX = int(int16(base.BaseDX))
	staged.MV = int(base.Mobility)
	staged.HP = int(int16(base.MaxHP))
	staged.MaxHP = staged.HP
	staged.MP = int(int16(base.MaxMP))
	staged.MaxMP = staged.MP
	staged.NativeRecordWord42, staged.HasNativeRecordWord42 = base.MaxHP, true
	staged.NativeRecordWord46, staged.HasNativeRecordWord46 = base.MaxMP, true
	if staged.NativeRecordByte6 == 2 {
		staged.Exp = 0
	} else {
		staged.Exp = 0xff
	}
	*unit = staged
	return nil
}

func mulWord(value, multiplier byte) uint16 {
	return uint16(uint32(value) * uint32(multiplier))
}

func addScaledWord(base uint16, value byte, multiplier int32) uint16 {
	return uint16(int32(base) + int32(value)*multiplier)
}
