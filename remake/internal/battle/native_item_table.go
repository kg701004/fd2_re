package battle

import (
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
)

type nativeItemEffectRowJSON struct {
	ID  int    `json:"id"`
	Raw string `json:"raw"`
}

// LoadNativeItemEffectRowPrefix loads an explicitly bounded prefix of the raw
// 0x4e56c table. Rows must be consecutive and exactly 0x17 bytes. The function
// deliberately does not infer that the fixture's final ID is the native table
// boundary.
func LoadNativeItemEffectRowPrefix(path string) ([]byte, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read native item effect rows: %w", err)
	}
	var encoded []nativeItemEffectRowJSON
	if err := json.Unmarshal(data, &encoded); err != nil {
		return nil, fmt.Errorf("decode native item effect rows: %w", err)
	}
	if len(encoded) == 0 || len(encoded) > 0x100 {
		return nil, fmt.Errorf("native item effect row count %d is invalid", len(encoded))
	}
	table := make([]byte, len(encoded)*NativeItemEffectRowSize)
	for i, row := range encoded {
		if row.ID != i {
			return nil, fmt.Errorf("native item effect row %d has id %d", i, row.ID)
		}
		raw, err := hex.DecodeString(row.Raw)
		if err != nil {
			return nil, fmt.Errorf("decode native item effect row %d: %w", i, err)
		}
		if len(raw) != NativeItemEffectRowSize {
			return nil, fmt.Errorf(
				"native item effect row %d has %d bytes, want %d",
				i, len(raw), NativeItemEffectRowSize,
			)
		}
		copy(table[i*NativeItemEffectRowSize:], raw)
	}
	return table, nil
}
