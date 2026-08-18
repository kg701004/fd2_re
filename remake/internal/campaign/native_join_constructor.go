package campaign

import (
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

const (
	nativeJoinEXESize   = 357074
	nativeJoinEXEMD5    = "b97caf2239a27a896069d03549d96e1e"
	nativeJoinEXESHA256 = "222b7d067ad4450eb9c5f6e6bce1797d54bb050417ba39ced6067f8039f28c4f"
)

// NativeJoinConstructorTable is the address-preserving projection of the
// 32-row tables consumed by original sub_112A5. It deliberately does not reuse
// the unrelated FDFIELD constructor table.
type NativeJoinConstructorTable struct {
	rows map[int]nativeJoinConstructorRow
}

type nativeJoinConstructorRow struct {
	defaults [0x18]byte
	growth   [0x0b]byte
}

// LoadNativeJoinConstructorTable validates the executable identity, row order,
// source offsets and raw strides before exposing any constructor row.
func LoadNativeJoinConstructorTable(path string) (NativeJoinConstructorTable, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return NativeJoinConstructorTable{}, err
	}
	var wire struct {
		SchemaVersion int `json:"schema_version"`
		Source        struct {
			EXESize   int    `json:"exe_size"`
			EXEMD5    string `json:"exe_md5"`
			EXESHA256 string `json:"exe_sha256"`
		} `json:"source"`
		EvidenceLevel string `json:"evidence_level"`
		Rows          []struct {
			ID                int    `json:"id"`
			DefaultFileOffset string `json:"default_file_offset"`
			GrowthFileOffset  string `json:"growth_file_offset"`
			DefaultRaw        string `json:"default_raw"`
			GrowthRaw         string `json:"growth_raw"`
		} `json:"rows"`
	}
	if err := json.Unmarshal(raw, &wire); err != nil {
		return NativeJoinConstructorTable{}, err
	}
	if wire.SchemaVersion != 1 || wire.Source.EXESize != nativeJoinEXESize ||
		wire.Source.EXEMD5 != nativeJoinEXEMD5 || wire.Source.EXESHA256 != nativeJoinEXESHA256 ||
		wire.EvidenceLevel != "已證實" || len(wire.Rows) != 32 {
		return NativeJoinConstructorTable{}, fmt.Errorf("native JOIN constructor manifest identity is invalid")
	}

	table := NativeJoinConstructorTable{rows: make(map[int]nativeJoinConstructorRow, 32)}
	for index, source := range wire.Rows {
		if source.ID != index {
			return NativeJoinConstructorTable{}, fmt.Errorf("native JOIN row %d is not position-indexed", index)
		}
		defaultOffset, err := parseNativeJoinOffset(source.DefaultFileOffset)
		if err != nil || defaultOffset != 0x55ba1+index*0x18 {
			return NativeJoinConstructorTable{}, fmt.Errorf("native JOIN row %d default offset is invalid", index)
		}
		growthOffset, err := parseNativeJoinOffset(source.GrowthFileOffset)
		if err != nil || growthOffset != 0x55ea1+index*0x0b {
			return NativeJoinConstructorTable{}, fmt.Errorf("native JOIN row %d growth offset is invalid", index)
		}
		defaultRaw, err := hex.DecodeString(source.DefaultRaw)
		if err != nil || len(defaultRaw) != 0x18 {
			return NativeJoinConstructorTable{}, fmt.Errorf("native JOIN row %d default stride is invalid", index)
		}
		growthRaw, err := hex.DecodeString(source.GrowthRaw)
		if err != nil || len(growthRaw) != 0x0b {
			return NativeJoinConstructorTable{}, fmt.Errorf("native JOIN row %d growth stride is invalid", index)
		}
		var row nativeJoinConstructorRow
		copy(row.defaults[:], defaultRaw)
		copy(row.growth[:], growthRaw)
		table.rows[index] = row
	}
	return table, nil
}

func parseNativeJoinOffset(value string) (int, error) {
	parsed, err := strconv.ParseInt(strings.TrimPrefix(value, "0x"), 16, 32)
	return int(parsed), err
}

func nativeJoinWord(raw []byte, offset int) int {
	return int(raw[offset]) | int(raw[offset+1])<<8
}

// MaterializePersistentUnit transcribes the proven sub_112A5 writes into a
// local persistent record and runs its sub_1145A equipment tail. The local
// record is transaction staging, not a claim that untouched bytes of every
// native 0x50-byte record are known. No Unit is returned unless the raw item
// rows needed by every equipped slot are available.
func (table NativeJoinConstructorTable) MaterializePersistentUnit(
	id int,
	base battle.Unit,
	itemTable []byte,
) (battle.Unit, error) {
	row, ok := table.rows[id]
	if !ok || id < 0 || id > 0xff {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d has no proven constructor row", id)
	}
	level := int(row.defaults[2])
	if level <= 0 {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d has invalid level %d", id, level)
	}
	maxHP := nativeJoinWord(row.defaults[:], 3) + int(row.growth[6])*(level-1)
	maxMP := nativeJoinWord(row.defaults[:], 5) + int(row.growth[8])*(level-1)
	if maxHP < 0 || maxHP > 0xffff || maxMP < 0 || maxMP > 0xffff {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d HP/MP exceeds raw word", id)
	}

	var record [0x50]byte
	record[5] = 0
	record[6] = 2
	record[7] = byte(id)
	record[8] = byte(id)
	record[9] = 0
	record[0x0a], record[0x0b] = 0x40, row.defaults[0x0c]
	record[0x0c], record[0x0d] = 0x40, row.defaults[0x0d]
	for slot := 0; slot < 4; slot++ {
		item := row.defaults[0x0e+slot]
		cell := 0x0e + slot*2
		if item == 0xff {
			record[cell] = 0x80
		}
		record[cell+1] = item
	}
	record[0x16], record[0x18] = 0x80, 0x80
	copy(record[0x1a:0x1e], row.defaults[8:12])
	record[0x1e] = 0
	record[0x1f] = row.defaults[0]
	record[0x20] = row.defaults[1]
	record[0x21] = byte(level)
	record[0x31] = 0xff
	baseAP := nativeJoinWord(row.defaults[:], 0x12) + int(row.growth[0])*level
	baseDP := nativeJoinWord(row.defaults[:], 0x14) + int(row.growth[2])*level
	baseDX := nativeJoinWord(row.defaults[:], 0x16) + int(row.growth[4])*level
	binary.LittleEndian.PutUint16(record[0x37:], uint16(baseAP))
	binary.LittleEndian.PutUint16(record[0x39:], uint16(baseDP))
	record[0x3b] = row.defaults[7]
	record[0x3c] = 0
	binary.LittleEndian.PutUint16(record[0x3e:], uint16(baseDX))
	binary.LittleEndian.PutUint16(record[0x40:], uint16(maxHP))
	binary.LittleEndian.PutUint16(record[0x42:], uint16(maxHP))
	binary.LittleEndian.PutUint16(record[0x44:], uint16(maxMP))
	binary.LittleEndian.PutUint16(record[0x46:], uint16(maxMP))
	if err := battle.ApplyNativeEquipmentRecalc(record[:], itemTable); err != nil {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d equipment: %w", id, err)
	}

	unit := base
	unit.Camp = battle.Own
	unit.Lv = level
	unit.HP, unit.MaxHP = maxHP, maxHP
	unit.MP, unit.MaxMP = maxMP, maxMP
	unit.MV = int(row.defaults[7])
	unit.Exp = 0
	unit.AP = int(int16(binary.LittleEndian.Uint16(record[0x48:])))
	unit.DP = int(int16(binary.LittleEndian.Uint16(record[0x4a:])))
	unit.HIT = int(int16(binary.LittleEndian.Uint16(record[0x4c:])))
	unit.EV = int(int16(binary.LittleEndian.Uint16(record[0x4e:])))
	unit.DX = int(int16(binary.LittleEndian.Uint16(record[0x3e:])))
	unit.BaseAP = int(int16(binary.LittleEndian.Uint16(record[0x37:])))
	unit.BaseDP = int(int16(binary.LittleEndian.Uint16(record[0x39:])))
	unit.BaseHIT, unit.BaseEV = unit.DX, unit.DX
	unit.BaseMV = int(record[0x3b])
	unit.BaseAtkMin, unit.BaseAtkMax = base.AtkMin, base.AtkMax
	unit.EquipmentBaseSet = true
	unit.ClassID = int(row.defaults[1])
	unit.NativeRecordRace, unit.HasNativeRecordRace = row.defaults[0], true
	unit.NativeRecordClass, unit.HasNativeRecordClass = row.defaults[1], true
	unit.NativeRecordByte5, unit.HasNativeRecordByte5 = 0, true
	unit.NativeRecordByte6, unit.HasNativeRecordByte6 = 2, true
	unit.NativeIdentity, unit.HasNativeIdentity = id, true
	unit.NativeRecordByte8, unit.HasNativeRecordByte8 = byte(id), true
	unit.MapSelectorKey, unit.HasMapSelectorKey = id, true
	unit.BattleFig, unit.HasBattleFig = id, true
	unit.NativeCommandMask = [5]byte{}
	copy(unit.NativeCommandMask[:4], row.defaults[8:12])
	unit.NativeTransient = [6]byte{}
	unit.NativeRecordWord42, unit.HasNativeRecordWord42 = uint16(maxHP), true
	unit.NativeRecordWord46, unit.HasNativeRecordWord46 = uint16(maxMP), true
	// The class-table `record` buffer built above never writes +0x34/0x35/0x36
	// (confirmed against the Ghidra decompile: those three bytes are only
	// ever written by the separate FDFIELD-driven enemy/NPC deployment
	// constructor, and only ever read back by the 0x13A9F AI dispatcher,
	// which never runs for a JOINed Own-camp character). 0 matches the
	// record slot's actual zero-initialized state, not a guess.
	unit.NativeRecordByte34, unit.HasNativeRecordByte34 = 0, true
	unit.NativeRecordByte35, unit.HasNativeRecordByte35 = 0, true
	unit.NativeRecordByte36, unit.HasNativeRecordByte36 = 0, true
	unit.Inventory = nil
	unit.Equipped = nil
	unit.InventorySlots = make([]int, 8)
	unit.NativeInventoryFlags = make([]int, 8)
	for slot := 0; slot < 8; slot++ {
		cell := 0x0a + slot*2
		flags, item := record[cell], record[cell+1]
		unit.InventorySlots[slot] = int(item)
		unit.NativeInventoryFlags[slot] = int(flags)
		if int8(flags) < 0 {
			continue
		}
		unit.Inventory = append(unit.Inventory, int(item))
		unit.Equipped = append(unit.Equipped, flags&0x40 != 0)
	}
	return unit, nil
}
