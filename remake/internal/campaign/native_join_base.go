package campaign

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

const nativeJoinBaseEXESHA256 = "222b7d067ad4450eb9c5f6e6bce1797d54bb050417ba39ced6067f8039f28c4f"

// NativeJoinBaseTable names decoded map records that supply the visual/base
// fields for a native sub_112A5 JOIN when that character is not present in the
// current runtime array.  The constructor statistics still come from
// native_join_constructor.json; this table only preserves an explicit source
// for fields that sub_112A5 receives from its character data helpers.
type NativeJoinBaseTable struct {
	rows      map[int]nativeJoinBaseRow
	sourceDir string
}

type nativeJoinBaseRow struct {
	Roster    string
	UnitIndex int
	RawByte8  int
}

// LoadNativeJoinBaseTable validates a small, evidence-labelled map-record
// index.  It never searches arbitrary maps or infers Fig==character ID.
func LoadNativeJoinBaseTable(path string) (NativeJoinBaseTable, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return NativeJoinBaseTable{}, err
	}
	var wire struct {
		SchemaVersion int `json:"schema_version"`
		Source        struct {
			EXESHA256 string `json:"exe_sha256"`
		} `json:"source"`
		EvidenceLevel string `json:"evidence_level"`
		Rows          []struct {
			ID        int    `json:"id"`
			Roster    string `json:"roster"`
			UnitIndex int    `json:"unit_index"`
			RawByte8  int    `json:"raw_byte8"`
		} `json:"rows"`
	}
	if err := json.Unmarshal(raw, &wire); err != nil {
		return NativeJoinBaseTable{}, err
	}
	if wire.SchemaVersion != 1 || wire.Source.EXESHA256 != nativeJoinBaseEXESHA256 ||
		wire.EvidenceLevel != "強推論" || len(wire.Rows) == 0 {
		return NativeJoinBaseTable{}, fmt.Errorf("native JOIN base manifest identity is invalid")
	}
	table := NativeJoinBaseTable{rows: make(map[int]nativeJoinBaseRow, len(wire.Rows)), sourceDir: filepath.Dir(path)}
	for _, row := range wire.Rows {
		if !JoinableCharacterID(row.ID) || row.Roster == "" || row.UnitIndex < 0 || row.RawByte8 < 0 || row.RawByte8 > 0xff || row.RawByte8 != row.ID {
			return NativeJoinBaseTable{}, fmt.Errorf("native JOIN base row %d is invalid", row.ID)
		}
		if _, exists := table.rows[row.ID]; exists {
			return NativeJoinBaseTable{}, fmt.Errorf("native JOIN base row %d repeats", row.ID)
		}
		table.rows[row.ID] = nativeJoinBaseRow{Roster: row.Roster, UnitIndex: row.UnitIndex, RawByte8: row.RawByte8}
	}
	return table, nil
}

// LoadBaseUnit returns only the explicitly indexed decoded map record and
// verifies its independent raw +8 provenance before it can seed JOIN.
func (table NativeJoinBaseTable) LoadBaseUnit(id int) (battle.Unit, error) {
	row, ok := table.rows[id]
	if !ok {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d has no proven base record", id)
	}
	state, err := battle.Load(filepath.Join(table.sourceDir, row.Roster))
	if err != nil {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d base roster: %w", id, err)
	}
	if row.UnitIndex >= len(state.Units) || state.Units[row.UnitIndex] == nil {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d base unit index %d is unavailable", id, row.UnitIndex)
	}
	base := *state.Units[row.UnitIndex]
	if base.Camp != battle.Ally && base.Camp != battle.Own {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d base unit is not allied", id)
	}
	if !base.HasNativeRecordByte8 || int(base.NativeRecordByte8) != row.RawByte8 {
		return battle.Unit{}, fmt.Errorf("native JOIN character %d base record lacks raw +8=%d", id, row.RawByte8)
	}
	return base, nil
}
