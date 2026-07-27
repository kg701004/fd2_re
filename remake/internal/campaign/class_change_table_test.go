package campaign

import (
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func classChangeFixture(t *testing.T) ClassChangeTable {
	t.Helper()
	path := filepath.Join("..", "..", "..", "docs", "data", "exe_tables", "class_change_targets.json")
	table, err := LoadClassChangeTable(path)
	if err != nil {
		t.Fatal(err)
	}
	return table
}

func TestClassChangeTableSeparatesCurrentAndTargetIndexes(t *testing.T) {
	table := classChangeFixture(t)
	if len(table.Current) != 0x12 || len(table.Targets) != 0x22 {
		t.Fatalf("table lengths current=%d target=%d", len(table.Current), len(table.Targets))
	}
	for i := 0; i < 0x12; i++ {
		row, ok := table.Current[i]
		if !ok {
			t.Fatalf("missing current row %d", i)
		}
		if row.Portrait != i || row.DefaultTarget != i+0x20 {
			t.Fatalf("current row %d=%+v", i, row)
		}
		if row.ItemID == 0xff && row.OptionalTarget != nil {
			t.Fatalf("raw ff item unexpectedly has optional target: %+v", row)
		}
	}
	if table.Current[9].OptionalTarget == nil || *table.Current[9].OptionalTarget != 0x3b {
		t.Fatalf("portrait 9 optional target=%v, want 0x3b", table.Current[9].OptionalTarget)
	}
	for i := 0; i < 0x22; i++ {
		row, ok := table.Targets[i+0x20]
		if !ok || row.Portrait != i+0x20 {
			t.Fatalf("target row %d=%+v", i+0x20, row)
		}
	}
}

func TestNativeClassChangeTargetUsesOriginalOverwritePriority(t *testing.T) {
	table := classChangeFixture(t)
	u := &battle.Unit{Portrait: 9, Inventory: []int{0x5a, 0x58}}
	got, ok := NativeClassChangeTarget(u, table)
	if !ok || got.Branch != "special" || got.RequiredItemID != 0x5a || got.InventoryIndex != 0 || got.Portrait != 0x34 {
		t.Fatalf("special override=%+v ok=%v", got, ok)
	}
	u.Inventory = []int{0x58}
	got, ok = NativeClassChangeTarget(u, table)
	if !ok || got.Branch != "optional" || got.RequiredItemID != 0x58 || got.InventoryIndex != 0 || got.Portrait != 0x3b {
		t.Fatalf("optional override=%+v ok=%v", got, ok)
	}
	u.Inventory = nil
	got, ok = NativeClassChangeTarget(u, table)
	if !ok || got.Branch != "default" || got.RequiredItemID != -1 || got.InventoryIndex != -1 || got.Portrait != 0x29 {
		t.Fatalf("default target=%+v ok=%v", got, ok)
	}
}

func TestLoadClassChangeGrowthMapsRowsByPortraitIndex(t *testing.T) {
	path := filepath.Join("..", "..", "..", "docs", "data", "exe_tables", "growth.json")
	growth, err := LoadClassChangeGrowth(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(growth) != 36 {
		t.Fatalf("growth rows=%d, want 36 rows idx>=32", len(growth))
	}
	if growth[0x20].AP != [2]int{8, 12} || growth[0x41].MP != [2]int{0, 0} {
		t.Fatalf("unexpected mapped growth rows: 0x20=%+v 0x41=%+v", growth[0x20], growth[0x41])
	}
}
