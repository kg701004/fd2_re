package ending

import (
	"path/filepath"
	"testing"
)

func TestLoadMontageTailPlansProvenanceBoundRawTables(t *testing.T) {
	tail, err := LoadMontageTail(filepath.Join("..", "..", "assets", "endings", "native_2c194_tail.json"))
	if err != nil {
		t.Fatal(err)
	}
	entries, err := tail.Plan()
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 20 || entries[0] != (MontageTailEntry{Index: 0, Global540FF: 4, UnitPlus7: 51, UnitPlus14: 103, UnitByte6: 0}) || entries[19] != (MontageTailEntry{Index: 19, Global540FF: 47, UnitPlus7: 126, UnitPlus14: 50, UnitByte6: 2}) {
		t.Fatalf("unexpected raw tail plan: first=%#v last=%#v", entries[0], entries[len(entries)-1])
	}
}

func TestMontageTailRejectsShortOrNonByteRawTable(t *testing.T) {
	tail := MontageTail{Loop: MontageTailLoop{Count: 2}, RawTables: MontageTailRawTable{Global540FF: []int{1}, UnitPlus7: []int{1, 2}, UnitPlus14: []int{1, 2}}}
	if _, err := tail.Plan(); err == nil {
		t.Fatal("short raw table accepted")
	}
	tail.RawTables.Global540FF = []int{1, 0x100}
	tail.RawTables.UnitPlus7 = []int{1, 2}
	if _, err := tail.Plan(); err == nil {
		t.Fatal("non-byte raw table accepted")
	}
}
