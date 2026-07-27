package battle

import "testing"

func TestApplyNativeItemCapacityToUnitPreservesCurrentAndEXP(t *testing.T) {
	u := &Unit{
		HP: 40, MaxHP: 100, MP: 7, MaxMP: 20, MV: 255, Exp: 73,
		EquipmentBaseSet: true, BaseMV: 255,
		Inventory: []int{96, 0x20}, Equipped: []bool{false, false},
		InventorySlots:       []int{96, 0x20, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0, 0, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	route, _ := NativeItemCapacityStepRouteForType(19, 1)
	got, err := ApplyNativeItemCapacityToUnit(u, u, route, 0)
	if err != nil {
		t.Fatal(err)
	}
	if got != 0 || u.MV != 0 || u.BaseMV != 0 || u.Exp != 73 ||
		u.HP != 40 || u.MaxHP != 100 || u.MP != 7 || u.MaxMP != 20 {
		t.Fatalf("capacity projection mismatch: %#v", u)
	}
	if len(u.Inventory) != 1 || u.Inventory[0] != 0x20 || u.InventorySlots[0] != 0x20 {
		t.Fatalf("capacity item was not compact-removed: %#v", u)
	}
}

func TestApplyNativeItemCapacityToUnitAddsMaximumOnly(t *testing.T) {
	u := &Unit{
		HP: 40, MaxHP: 100,
		Inventory:            []int{94},
		InventorySlots:       []int{94, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	route, _ := NativeItemCapacityStepRouteForType(17, 20)
	got, err := ApplyNativeItemCapacityToUnit(u, u, route, 0)
	if err != nil || got != 120 || u.MaxHP != 120 || u.HP != 40 {
		t.Fatalf("got=%d err=%v unit=%#v", got, err, u)
	}
}
