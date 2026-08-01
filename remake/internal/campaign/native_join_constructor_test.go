package campaign

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func TestNativeJoinConstructorMaterializesKeliFromRawTables(t *testing.T) {
	table, err := LoadNativeJoinConstructorTable(filepath.Join("..", "..", "assets", "data", "native_join_constructor.json"))
	if err != nil {
		t.Fatal(err)
	}
	unit, err := table.MaterializePersistentUnit(12, battle.Unit{
		Name: "凱麗", HP: 90, MaxHP: 90, MP: 7, MaxMP: 7, AP: 44, DP: 33,
	})
	if err != nil {
		t.Fatal(err)
	}
	if unit.Name != "凱麗" || unit.Lv != 10 || unit.ClassID != 8 || unit.MV != 5 ||
		unit.HP != 151 || unit.MaxHP != 151 || unit.MP != 0 || unit.MaxMP != 0 ||
		unit.NativeRecordWord42 != 151 || !unit.HasNativeRecordWord42 ||
		unit.NativeRecordWord46 != 0 || !unit.HasNativeRecordWord46 ||
		unit.NativeIdentity != 12 || !unit.HasNativeIdentity ||
		unit.MapSelectorKey != 12 || !unit.HasMapSelectorKey ||
		unit.BattleFig != 12 || !unit.HasBattleFig {
		t.Fatalf("unexpected Keli JOIN projection: %+v", unit)
	}
	// sub_1145A is not part of this slice; unrelated normalized combat fields
	// remain on the editable base rather than being guessed.
	if unit.AP != 44 || unit.DP != 33 {
		t.Fatalf("unclosed equipment recomputation was overwritten: AP=%d DP=%d", unit.AP, unit.DP)
	}
}

func TestNativeJoinConstructorRejectsWrongExecutableIdentity(t *testing.T) {
	path := filepath.Join(t.TempDir(), "join.json")
	if err := os.WriteFile(path, []byte(`{"schema_version":1,"source":{"exe_size":1},"evidence_level":"已證實","rows":[]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadNativeJoinConstructorTable(path); err == nil {
		t.Fatal("wrong executable identity was accepted")
	}
}

func TestNativeJoinConstructorRejectsUnknownIdentity(t *testing.T) {
	table, err := LoadNativeJoinConstructorTable(filepath.Join("..", "..", "assets", "data", "native_join_constructor.json"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := table.MaterializePersistentUnit(32, battle.Unit{}); err == nil {
		t.Fatal("unknown JOIN identity was accepted")
	}
}

func TestNativeJoinConstructorRejectsOffsetDrift(t *testing.T) {
	source := filepath.Join("..", "..", "assets", "data", "native_join_constructor.json")
	raw, err := os.ReadFile(source)
	if err != nil {
		t.Fatal(err)
	}
	tampered := bytes.Replace(raw, []byte(`"default_file_offset": "0x55ba1"`), []byte(`"default_file_offset": "0x55ba2"`), 1)
	if bytes.Equal(raw, tampered) {
		t.Fatal("fixture did not contain row-zero source offset")
	}
	path := filepath.Join(t.TempDir(), "join.json")
	if err := os.WriteFile(path, tampered, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadNativeJoinConstructorTable(path); err == nil {
		t.Fatal("shifted source offset was accepted")
	}
}
