package battle

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
)

// NativeCommandRecord is the verified 7-byte 0x4e516 record for IDs 0..35.
// The field names intentionally describe only their proven call-site roles:
// generic 0x1cff0 uses SelectionMode (+3) from the actor, then EffectMode
// (+4) from the confirmed cursor; +5 is MP cost and +6 is target code.
// It is not the normalized Spell gameplay model.
type NativeCommandRecord struct {
	ID            int
	Damage        int
	Hit           int
	SelectionMode int
	EffectMode    int
	MPCost        int
	TargetCode    int
}

type nativeCommandRecordJSON struct {
	ID     int    `json:"id"`
	Dmg    int    `json:"dmg"`
	Hit    int    `json:"hit"`
	Dist   int    `json:"dist"`
	Range  int    `json:"range"`
	MP     int    `json:"mp"`
	Target int    `json:"target"`
	Raw    string `json:"raw"`
}

// LoadNativeCommandRecords loads only the byte-identical EXE command slice.
// Existing spells.json is accepted as its physical export, but each editable
// presentation field must agree with its raw 7-byte source.  This prevents a
// later normalized spell edit from silently changing native command behavior.
func LoadNativeCommandRecords(path string) ([]NativeCommandRecord, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var rows []nativeCommandRecordJSON
	if err := json.Unmarshal(raw, &rows); err != nil {
		return nil, err
	}
	if len(rows) != 36 {
		return nil, fmt.Errorf("native command records len=%d want 36", len(rows))
	}
	result := make([]NativeCommandRecord, len(rows))
	for i, row := range rows {
		if row.ID != i {
			return nil, fmt.Errorf("native command id=%d at index=%d", row.ID, i)
		}
		bytes, err := hex.DecodeString(row.Raw)
		if err != nil || len(bytes) != 7 {
			return nil, fmt.Errorf("native command id=%d invalid raw", row.ID)
		}
		damage := int(bytes[0]) | int(bytes[1])<<8
		if row.Dmg != damage || row.Hit != int(bytes[2]) || row.Dist != int(bytes[3]) || row.Range != int(bytes[4]) || row.MP != int(bytes[5]) || row.Target != int(bytes[6]) {
			return nil, fmt.Errorf("native command id=%d fields disagree with raw", row.ID)
		}
		result[i] = NativeCommandRecord{
			ID: row.ID, Damage: damage, Hit: int(bytes[2]), SelectionMode: int(bytes[3]),
			EffectMode: int(bytes[4]), MPCost: int(bytes[5]), TargetCode: int(bytes[6]),
		}
	}
	return result, nil
}
