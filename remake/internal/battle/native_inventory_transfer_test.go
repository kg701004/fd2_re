package battle

import "testing"

func TestTransferNativeInventoryItemUsesFirstDestinationHole(t *testing.T) {
	source := &Unit{Inventory: []int{0x44, 0x55}, Equipped: []bool{false, true}, InventorySlots: []int{0x44, 0x55, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}, NativeInventoryFlags: []int{0, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80}}
	destination := &Unit{Inventory: []int{0x10}, Equipped: []bool{true}, InventorySlots: []int{0xff, 0x10, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}, NativeInventoryFlags: []int{0x80, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80}}
	if err := TransferNativeInventoryItem(source, 0, destination); err != nil {
		t.Fatal(err)
	}
	if len(source.Inventory) != 1 || source.Inventory[0] != 0x55 || source.InventorySlots[0] != 0x55 {
		t.Fatalf("source was not compactly removed: inventory=%v slots=%v", source.Inventory, source.InventorySlots)
	}
	if len(destination.Inventory) != 2 || destination.Inventory[1] != 0x44 || destination.InventorySlots[0] != 0x44 || destination.Equipped[1] {
		t.Fatalf("destination did not receive unequipped item in first hole: inventory=%v slots=%v equipped=%v", destination.Inventory, destination.InventorySlots, destination.Equipped)
	}
	if source.NativeInventoryFlags[0] != 0x40 || destination.NativeInventoryFlags[0] != 0 {
		t.Fatalf("native flags did not shift/clear: source=%v destination=%v", source.NativeInventoryFlags, destination.NativeInventoryFlags)
	}
}

func TestTransferNativeInventoryItemFullDestinationIsAtomic(t *testing.T) {
	source := &Unit{
		Inventory: []int{0x44}, Equipped: []bool{false},
		InventorySlots:       []int{0x44, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	destination := &Unit{
		Inventory:            []int{1, 2, 3, 4, 5, 6, 7, 8},
		Equipped:             []bool{false, false, false, false, false, false, false, false},
		InventorySlots:       []int{1, 2, 3, 4, 5, 6, 7, 8},
		NativeInventoryFlags: []int{0, 0, 0, 0, 0, 0, 0, 0},
	}
	if err := TransferNativeInventoryItem(source, 0, destination); err == nil {
		t.Fatal("full destination unexpectedly accepted transfer")
	}
	if len(source.Inventory) != 1 || source.Inventory[0] != 0x44 || len(destination.Inventory) != 8 {
		t.Fatalf("failed transfer mutated units: source=%v destination=%v", source.Inventory, destination.Inventory)
	}
}

func TestTransferNativeInventoryItemRejectsDivergentProjection(t *testing.T) {
	source := &Unit{
		Inventory: []int{0x44}, Equipped: []bool{false},
		InventorySlots:       []int{0x55, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	destination := &Unit{
		InventorySlots:       []int{0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	if err := TransferNativeInventoryItem(source, 0, destination); err == nil {
		t.Fatal("divergent native projection was accepted")
	}
	if source.Inventory[0] != 0x44 || len(destination.Inventory) != 0 {
		t.Fatal("failed strict transfer mutated units")
	}
}

func TestTransferNativeInventoryItemAllowsNativeSelfReorder(t *testing.T) {
	unit := &Unit{
		Inventory:            []int{0x44, 0x55, 0x66},
		Equipped:             []bool{true, false, true},
		InventorySlots:       []int{0x44, 0x55, 0x66, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0x40, 0, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	if err := TransferNativeInventoryItem(unit, 0, unit); err != nil {
		t.Fatal(err)
	}
	if got := unit.Inventory; len(got) != 3 ||
		got[0] != 0x55 || got[1] != 0x66 || got[2] != 0x44 {
		t.Fatalf("self transfer inventory=%#v", got)
	}
	if got := unit.Equipped; len(got) != 3 ||
		got[0] || !got[1] || got[2] {
		t.Fatalf("self transfer equipped=%#v", got)
	}
	if got := unit.NativeInventoryFlags; got[0] != 0 ||
		got[1] != 0x40 || got[2] != 0 || got[3] != 0x80 {
		t.Fatalf("self transfer flags=%#v", got)
	}
}
