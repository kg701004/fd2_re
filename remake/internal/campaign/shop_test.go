package campaign

import (
	"path/filepath"
	"reflect"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func TestBuyGoodUsesSelectedInventoryAndIsAtomicOnFailure(t *testing.T) {
	good := Good{ID: 0xc0, Name: "藥草", Price: 10}
	receiver := &battle.Unit{Inventory: []int{1, 2}}
	gold, err := BuyGood(50, receiver, good)
	if err != nil || gold != 40 || !reflect.DeepEqual(receiver.Inventory, []int{1, 2, 0xc0}) {
		t.Fatalf("purchase gold=%d err=%v inventory=%#v", gold, err, receiver.Inventory)
	}

	full := &battle.Unit{Inventory: make([]int, 8)}
	if got, err := BuyGood(50, full, good); err == nil || got != 50 || len(full.Inventory) != 8 {
		t.Fatalf("full inventory changed gold=%d err=%v inventory=%#v", got, err, full.Inventory)
	}
	if got, err := BuyGood(9, receiver, good); err == nil || got != 9 || len(receiver.Inventory) != 3 {
		t.Fatalf("insufficient gold changed state gold=%d err=%v inventory=%#v", got, err, receiver.Inventory)
	}
}

func TestReserveGoodDefersGoldUntilEquipDecision(t *testing.T) {
	receiver := &battle.Unit{}
	good := Good{ID: 0x80, Price: 25, Name: "劍"}
	slot, err := ReserveGood(30, receiver, good)
	if err != nil || slot != 0 || len(receiver.Inventory) != 1 || len(receiver.Equipped) != 1 || receiver.Equipped[0] {
		t.Fatalf("reserve slot=%d err=%v inventory=%#v equipped=%#v", slot, err, receiver.Inventory, receiver.Equipped)
	}
	if got := FinalizeGood(30, good); got != 5 {
		t.Fatalf("finalize gold=%d, want 5", got)
	}
}

func TestSellGoodPaysThreeQuartersAndRemovesSlot(t *testing.T) {
	u := &battle.Unit{Inventory: []int{7, 8}, Equipped: []bool{true, false}}
	gold, err := SellGood(10, u, 7, 101)
	if err != nil || gold != 85 || len(u.Inventory) != 1 || u.Inventory[0] != 8 || len(u.Equipped) != 1 || u.Equipped[0] {
		t.Fatalf("sell gold=%d err=%v inventory=%v equipped=%v", gold, err, u.Inventory, u.Equipped)
	}
}

func TestSellSlotTargetsDuplicateInventoryEntry(t *testing.T) {
	u := &battle.Unit{Inventory: []int{7, 7}, Equipped: []bool{true, false}}
	gold, err := SellSlot(0, u, 1, 100)
	if err != nil || len(u.Inventory) != 1 || len(u.Equipped) != 1 || !u.Equipped[0] || gold != 75 {
		t.Fatalf("slot sell gold=%d err=%v inventory=%v equipped=%v", gold, err, u.Inventory, u.Equipped)
	}
}

func TestSellNativeSlotCompactsRawCellsAndCreditsAfterValidation(t *testing.T) {
	u := battle.Unit{
		AP: 16, DP: 12, HIT: 97, EV: 2, MV: 4,
		BaseAP: 6, BaseDP: 4, BaseHIT: 2, BaseEV: 2, BaseMV: 4,
		EquipmentBaseSet: true,
		Inventory:        []int{0, 1, 132},
		Equipped:         []bool{true, false, true},
		InventorySlots:   []int{0, 1, 132, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{
			0x40, 0, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80,
		},
	}
	stats := map[int]ItemStats{
		0:   {Type: 1, AP: 10, HIT: 95},
		1:   {Type: 1, AP: 20, HIT: 95},
		132: {Type: 22, DP: 8},
	}
	gold, err := SellNativeSlot(100, &u, 1, 200, stats)
	if err != nil {
		t.Fatal(err)
	}
	if gold != 250 ||
		!reflect.DeepEqual(u.Inventory, []int{0, 132}) ||
		!reflect.DeepEqual(
			u.InventorySlots,
			[]int{0, 132, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		) ||
		!reflect.DeepEqual(
			u.NativeInventoryFlags,
			[]int{0x40, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
		) {
		t.Fatalf(
			"native sell = gold %d inventory %#v slots %#v flags %#v",
			gold, u.Inventory, u.InventorySlots, u.NativeInventoryFlags,
		)
	}
}

func TestLoadItemPricesFromRuntimeBundle(t *testing.T) {
	prices, err := LoadItemPrices("../../assets/data/item.json")
	if err != nil {
		t.Fatal(err)
	}
	if prices[0] != 50 || prices[0x80] != 50 {
		t.Fatalf("unexpected item prices: id0=%d id80=%d", prices[0], prices[0x80])
	}
}

func TestLoadShopEligibilityUsesOriginalTables(t *testing.T) {
	types, equip, err := LoadShopEligibility(filepath.Join("..", "..", "assets", "data", "item.json"), filepath.Join("..", "..", "assets", "data", "class_equip_types.json"))
	if err != nil || types[0x80] != 21 || !CanEquip(1, types[0x80], equip) || CanEquip(25, types[0x80], equip) {
		t.Fatalf("eligibility tables err=%v type=%d equip=%#v", err, types[0x80], equip[1])
	}
}

func TestCanEquipUsesOriginalClassTypeWhitelist(t *testing.T) {
	table := map[int][]int{1: {1, 21, 22, 255, 255, 255}, 25: {8, 27, 255, 255, 255, 255}}
	if !CanEquip(1, 21, table) || CanEquip(1, 8, table) || !CanEquip(25, 27, table) || CanEquip(0, 1, table) {
		t.Fatalf("class/type whitelist mismatch: %#v", table)
	}
}
