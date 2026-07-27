package battle

import (
	"encoding/binary"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestLoadTrackedNativeItemEffectRowPrefix(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	if got, want := len(table)/NativeItemEffectRowSize, 0xd7; got != want {
		t.Fatalf("row count = %d, want %d", got, want)
	}
	if got, want := table[:NativeItemEffectRowSize], []byte{
		0x01, 0x0a, 0x00, 0x5f, 0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x00, 0x00,
		0x00, 0x05, 0x00, 0x32, 0x00, 0x05, 0x00,
	}; string(got) != string(want) {
		t.Fatalf("row 0 = %x, want %x", got, want)
	}
}

func TestTrackedNativeEquipmentWordsMatchNormalizedItems(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile("../../assets/data/item.json")
	if err != nil {
		t.Fatal(err)
	}
	var items []struct {
		ID  int `json:"id"`
		AP  int `json:"ap"`
		Hit int `json:"hit"`
		DP  int `json:"dp"`
		EV  int `json:"ev"`
	}
	if err := json.Unmarshal(data, &items); err != nil {
		t.Fatal(err)
	}
	if got, want := len(items)*NativeItemEffectRowSize, len(table); got != want {
		t.Fatalf("normalized bytes = %d, raw table bytes = %d", got, want)
	}
	for i, item := range items {
		if item.ID != i {
			t.Fatalf("item row %d has id %d", i, item.ID)
		}
		row := table[i*NativeItemEffectRowSize:]
		got := [4]int{
			int(binary.LittleEndian.Uint16(row[1:3])),
			int(binary.LittleEndian.Uint16(row[3:5])),
			int(binary.LittleEndian.Uint16(row[5:7])),
			int(binary.LittleEndian.Uint16(row[7:9])),
		}
		want := [4]int{item.AP, item.Hit, item.DP, item.EV}
		if got != want {
			t.Fatalf("item %d raw equipment words = %v, normalized = %v", i, got, want)
		}
	}
}

func TestTrackedPermanentBaseStatItemRows(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		itemID int
		typ    byte
		amount uint16
		stat   NativeItemBaseStat
	}{
		{198, 8, 9, NativeItemBaseAP},
		{199, 9, 9, NativeItemBaseDP},
		{200, 0xa, 7, NativeItemBaseDX},
	}
	for _, tc := range cases {
		row := table[tc.itemID*NativeItemEffectRowSize:]
		if got := row[0x0d]; got != tc.typ {
			t.Fatalf("item %d effect type = %#x, want %#x", tc.itemID, got, tc.typ)
		}
		if got := binary.LittleEndian.Uint16(row[0x0e:]); got != tc.amount {
			t.Fatalf("item %d amount = %d, want %d", tc.itemID, got, tc.amount)
		}
		route, ok := NativeItemWordDeltaRouteForType(int(tc.typ))
		if !ok || route.BaseStat != tc.stat {
			t.Fatalf("item %d route = %#v, %v", tc.itemID, route, ok)
		}
	}
}

func TestTrackedHPRestoreItemRowsPreserveConsumptionBranch(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		itemID   int
		typ      byte
		amount   uint16
		consumes bool
	}{
		{192, 5, 40, true},
		{195, 5, 999, true},
		{211, 13, 200, false},
	}
	for _, tc := range cases {
		row := table[tc.itemID*NativeItemEffectRowSize:]
		typ := row[0x0d]
		amount := binary.LittleEndian.Uint16(row[0x0e:])
		if typ != tc.typ || amount != tc.amount {
			t.Fatalf("item %d type/amount = %#x/%d, want %#x/%d", tc.itemID, typ, amount, tc.typ, tc.amount)
		}
		route, ok := NativeItemHPRestoreRouteForType(typ, amount)
		if !ok || route.ConsumesSource != tc.consumes {
			t.Fatalf("item %d route = %#v, %v", tc.itemID, route, ok)
		}
	}
}

func TestLoadNativeItemEffectRowPrefixRejectsNonConsecutiveID(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rows.json")
	raw := `[{"id":1,"raw":"0000000000000000000000000000000000000000000000"}]`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	if _, err := LoadNativeItemEffectRowPrefix(path); err == nil {
		t.Fatal("expected non-consecutive id error")
	}
}
