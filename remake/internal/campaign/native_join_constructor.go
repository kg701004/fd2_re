package campaign

import (
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

// MaterializePersistentUnit applies only the sub_112A5 fields whose writers
// and consumers are closed. The subsequent sub_1145A equipment recomputation
// is not guessed; normalized combat fields outside this set stay on base.
func (table NativeJoinConstructorTable) MaterializePersistentUnit(id int, base battle.Unit) (battle.Unit, error) {
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

	unit := base
	unit.Camp = battle.Own
	unit.Lv = level
	unit.HP, unit.MaxHP = maxHP, maxHP
	unit.MP, unit.MaxMP = maxMP, maxMP
	unit.MV = int(row.defaults[7])
	unit.ClassID = int(row.defaults[1])
	unit.NativeRecordRace, unit.HasNativeRecordRace = row.defaults[0], true
	unit.NativeRecordClass, unit.HasNativeRecordClass = row.defaults[1], true
	unit.NativeIdentity, unit.HasNativeIdentity = id, true
	unit.NativeRecordByte8, unit.HasNativeRecordByte8 = byte(id), true
	unit.MapSelectorKey, unit.HasMapSelectorKey = id, true
	unit.BattleFig, unit.HasBattleFig = id, true
	copy(unit.NativeCommandMask[:4], row.defaults[8:12])
	unit.NativeRecordWord42, unit.HasNativeRecordWord42 = uint16(maxHP), true
	unit.NativeRecordWord46, unit.HasNativeRecordWord46 = uint16(maxMP), true
	return unit, nil
}
