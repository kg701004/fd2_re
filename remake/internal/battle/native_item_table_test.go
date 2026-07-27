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

func TestTrackedMPRestoreItemRows(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		itemID int
		amount uint16
	}{{206, 80}, {207, 200}} {
		row := table[tc.itemID*NativeItemEffectRowSize:]
		typ := row[0x0d]
		amount := binary.LittleEndian.Uint16(row[0x0e:])
		if typ != 11 || amount != tc.amount {
			t.Fatalf("item %d type/amount = %#x/%d, want 0xb/%d", tc.itemID, typ, amount, tc.amount)
		}
		if route, ok := NativeItemMPRestoreRouteForType(typ, amount); !ok || route.Amount != tc.amount {
			t.Fatalf("item %d MP route = %#v, %v", tc.itemID, route, ok)
		}
	}
}

func TestTrackedHITEVStepItemRow(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	row := table[210*NativeItemEffectRowSize:]
	if typ := row[0x0d]; typ != 12 {
		t.Fatalf("item 210 effect type = %#x, want 0xc", typ)
	}
	route, ok := NativeItemHITEVStepRouteForType(row[0x0d])
	if !ok || route.Increment != 15 || route.ConsumesSource {
		t.Fatalf("item 210 HIT/EV route = %#v, %v", route, ok)
	}
}

func TestTrackedAPDPModifierItemRows(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		itemID int
		typ    byte
		stat   NativeItemDerivedStat
	}{{213, 15, NativeItemDerivedDP}, {214, 16, NativeItemDerivedAP}} {
		row := table[tc.itemID*NativeItemEffectRowSize:]
		if row[0x0d] != tc.typ {
			t.Fatalf("item %d effect type = %#x, want %#x", tc.itemID, row[0x0d], tc.typ)
		}
		route, ok := NativeItemAPDPStepRouteForType(row[0x0d])
		if !ok || route.DerivedStat != tc.stat || route.ConsumesSource {
			t.Fatalf("item %d AP/DP route = %#v, %v", tc.itemID, route, ok)
		}
	}
}

func TestTrackedMarkerApplicationItemRows(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		itemID int
		typ    byte
		marker int
	}{{212, 14, 0x26}, {57, 22, 0x27}} {
		row := table[tc.itemID*NativeItemEffectRowSize:]
		if row[0x0d] != tc.typ {
			t.Fatalf("item %d effect type = %#x, want %#x", tc.itemID, row[0x0d], tc.typ)
		}
		route, ok := NativeItemMarkerApplicationRouteForType(row[0x0d])
		if !ok || route.MarkerOffset != tc.marker || route.ConsumesSource {
			t.Fatalf("item %d marker route = %#v, %v", tc.itemID, route, ok)
		}
	}
}

func TestTrackedMarkerClearRestoreItemRows(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		itemID int
		typ    byte
		marker int
	}{{196, 6, 0x25}, {197, 7, 0x26}} {
		row := table[tc.itemID*NativeItemEffectRowSize:]
		if row[0x0d] != tc.typ {
			t.Fatalf("item %d effect type = %#x, want %#x", tc.itemID, row[0x0d], tc.typ)
		}
		route, ok := NativeItemMarkerClearRestoreRouteForType(row[0x0d])
		if !ok || route.MarkerOffset != tc.marker || !route.ConsumesSource {
			t.Fatalf("item %d marker-clear route = %#v, %v", tc.itemID, route, ok)
		}
	}
}

func TestTrackedCapacityStepItemRows(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		itemID int
		typ    byte
		amount uint16
		stat   NativeItemCapacityStat
	}{{94, 17, 20, NativeItemMaxHP}, {95, 18, 20, NativeItemMaxMP}, {96, 19, 1, NativeItemMV}} {
		row := table[tc.itemID*NativeItemEffectRowSize:]
		typ := row[0x0d]
		amount := binary.LittleEndian.Uint16(row[0x0e:])
		if typ != tc.typ || amount != tc.amount {
			t.Fatalf("item %d type/amount = %#x/%d, want %#x/%d", tc.itemID, typ, amount, tc.typ, tc.amount)
		}
		route, ok := NativeItemCapacityStepRouteForType(typ, amount)
		if !ok || route.Stat != tc.stat || !route.ConsumesSource {
			t.Fatalf("item %d capacity route = %#v, %v", tc.itemID, route, ok)
		}
	}
}

func TestTrackedCommandDamageItemRows(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		itemID, commandID int
	}{{29, 6}, {38, 1}, {51, 7}, {99, 6}} {
		row := table[tc.itemID*NativeItemEffectRowSize:]
		typ := row[0x0d]
		commandID := binary.LittleEndian.Uint16(row[0x0e:])
		route, ok := NativeItemCommandDamageRouteForType(typ, commandID)
		if !ok || route.CommandID != tc.commandID || route.ConsumesSource {
			t.Fatalf("item %d command-damage route = %#v, %v", tc.itemID, route, ok)
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
