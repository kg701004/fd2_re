package battle

import (
	"encoding/json"
	"fmt"
	"os"
)

// CommandLearnEntry is one exact (required level, command ID) pair from the
// 12-byte native learning row selected by growth-row learn_idx.
type CommandLearnEntry struct {
	RequiredLevel int `json:"required_level"`
	CommandID     int `json:"command_id"`
}

type commandLearnFileRow struct {
	Idx     int                 `json:"idx"`
	Entries []CommandLearnEntry `json:"entries"`
}

// LoadCommandLearn reads the editable export of 0x626b3 + learn_idx*12.
// Rows must be dense and pairs strictly increasing by level so malformed
// authored data cannot silently grant a different native command.
func LoadCommandLearn(path string) (map[int][]CommandLearnEntry, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var rows []commandLearnFileRow
	if err := json.Unmarshal(raw, &rows); err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, fmt.Errorf("command learn: empty table")
	}
	out := make(map[int][]CommandLearnEntry, len(rows))
	for i, row := range rows {
		if row.Idx != i || len(row.Entries) > 6 {
			return nil, fmt.Errorf("command learn: invalid row %d", i)
		}
		previous := 0
		for _, entry := range row.Entries {
			if entry.RequiredLevel <= previous || entry.CommandID < 0 || entry.CommandID >= 40 {
				return nil, fmt.Errorf("command learn: invalid entry in row %d", i)
			}
			previous = entry.RequiredLevel
		}
		out[row.Idx] = append([]CommandLearnEntry(nil), row.Entries...)
	}
	return out, nil
}

func (s *State) learnNativeCommandsAtLevel(u *Unit) []int {
	if s == nil || u == nil || s.CommandLearn == nil {
		return nil
	}
	entries, ok := s.CommandLearn[u.Portrait]
	if !ok {
		return nil
	}
	var learned []int
	for _, entry := range entries {
		if entry.RequiredLevel == u.Lv && u.EnableNativeCommand(entry.CommandID) {
			learned = append(learned, entry.CommandID)
		}
	}
	return learned
}
