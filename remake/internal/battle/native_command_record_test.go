package battle

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadNativeCommandRecordsRuntimeExport(t *testing.T) {
	records, err := LoadNativeCommandRecords("../../assets/spells.json")
	if err != nil {
		t.Fatal(err)
	}
	if len(records) != 36 {
		t.Fatalf("records=%d", len(records))
	}
	got := records[0]
	if got.ID != 0 || got.Damage != 50 || got.Hit != 90 || got.SelectionMode != 5 || got.EffectMode != 0 || got.MPCost != 2 || got.TargetCode != 0 {
		t.Fatalf("command0=%+v", got)
	}
}

func TestLoadNativeCommandRecordsRejectsEditedPresentationMismatch(t *testing.T) {
	path := filepath.Join(t.TempDir(), "commands.json")
	data, err := os.ReadFile("../../assets/spells.json")
	if err != nil {
		t.Fatal(err)
	}
	data = []byte(strings.Replace(string(data), `"dmg": 50`, `"dmg": 51`, 1))
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadNativeCommandRecords(path); err == nil {
		t.Fatal("mismatched editable field must fail closed")
	}
}
