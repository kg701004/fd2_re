package battle

import "testing"

func TestApplyNativeItemBaseStatDeltaToUnitWrapsAndCompacts(t *testing.T) {
	u := &Unit{
		BaseAP: 32766, EquipmentBaseSet: true,
		Inventory: []int{0xc6, 0x20}, Equipped: []bool{false, true},
		InventorySlots:       []int{0xc6, 0x20, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	route, _ := NativeItemWordDeltaRouteForType(8)
	got, err := ApplyNativeItemBaseStatDeltaToUnit(u, u, route, 3, 0)
	if err != nil {
		t.Fatal(err)
	}
	if got != -32767 || u.BaseAP != -32767 {
		t.Fatalf("wrapped AP=%d/%d", got, u.BaseAP)
	}
	if len(u.Inventory) != 1 || u.Inventory[0] != 0x20 ||
		u.InventorySlots[0] != 0x20 || u.InventorySlots[7] != 0xff ||
		u.NativeInventoryFlags[0] != 0x40 || u.NativeInventoryFlags[7] != 0x80 {
		t.Fatalf("native compact removal failed: inventory=%v slots=%v flags=%v", u.Inventory, u.InventorySlots, u.NativeInventoryFlags)
	}
}

func TestApplyNativeItemBaseStatDeltaToUnitFailsAtomically(t *testing.T) {
	u := &Unit{
		BaseDP:               12,
		Inventory:            []int{0xc7},
		InventorySlots:       []int{0xc7, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	route, _ := NativeItemWordDeltaRouteForType(9)
	if _, err := ApplyNativeItemBaseStatDeltaToUnit(u, u, route, 9, 0); err == nil {
		t.Fatal("missing equipment-base provenance was accepted")
	}
	if u.BaseDP != 12 || len(u.Inventory) != 1 || u.InventorySlots[0] != 0xc7 {
		t.Fatalf("failed transaction mutated unit: %#v", u)
	}
}
