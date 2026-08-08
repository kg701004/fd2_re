package campaign

import (
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func TestNativeJoinBaseTableLoadsExplicitMap17Records(t *testing.T) {
	table, err := LoadNativeJoinBaseTable(filepath.Join("..", "..", "assets", "data", "native_join_base_units.json"))
	if err != nil {
		t.Fatal(err)
	}
	for _, id := range []int{7, 21} {
		unit, err := table.LoadBaseUnit(id)
		if err != nil {
			t.Fatalf("base %d: %v", id, err)
		}
		if unit.Camp != battle.Ally || !unit.HasNativeRecordByte8 || int(unit.NativeRecordByte8) != id || unit.Fig != id {
			t.Fatalf("base %d lost allied/raw identity: %#v", id, unit)
		}
	}
}

func TestNativeJoinBaseTableRejectsUnknownIdentity(t *testing.T) {
	table, err := LoadNativeJoinBaseTable(filepath.Join("..", "..", "assets", "data", "native_join_base_units.json"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := table.LoadBaseUnit(12); err == nil {
		t.Fatal("unindexed JOIN base was accepted")
	}
}
