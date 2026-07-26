package battle

import "testing"

func TestTransferNativeInventoryItemUsesFirstDestinationHole(t *testing.T) {
	source := &Unit{Inventory: []int{0x44, 0x55}, Equipped: []bool{false, true}, InventorySlots: []int{0x44, 0x55, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}}
	destination := &Unit{Inventory: []int{0x10}, Equipped: []bool{true}, InventorySlots: []int{0xff, 0x10, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}}
	if err := TransferNativeInventoryItem(source, 0, destination); err != nil {
		t.Fatal(err)
	}
	if len(source.Inventory) != 1 || source.Inventory[0] != 0x55 || source.InventorySlots[0] != 0x55 {
		t.Fatalf("source was not compactly removed: inventory=%v slots=%v", source.Inventory, source.InventorySlots)
	}
	if len(destination.Inventory) != 2 || destination.Inventory[1] != 0x44 || destination.InventorySlots[0] != 0x44 || destination.Equipped[1] {
		t.Fatalf("destination did not receive unequipped item in first hole: inventory=%v slots=%v equipped=%v", destination.Inventory, destination.InventorySlots, destination.Equipped)
	}
}

func TestTransferNativeInventoryItemFullDestinationIsAtomic(t *testing.T) {
	source := &Unit{Inventory: []int{0x44}, Equipped: []bool{false}, InventorySlots: []int{0x44, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}}
	destination := &Unit{Inventory: []int{1, 2, 3, 4, 5, 6, 7, 8}, InventorySlots: []int{1, 2, 3, 4, 5, 6, 7, 8}}
	if err := TransferNativeInventoryItem(source, 0, destination); err == nil {
		t.Fatal("full destination unexpectedly accepted transfer")
	}
	if len(source.Inventory) != 1 || source.Inventory[0] != 0x44 || len(destination.Inventory) != 8 {
		t.Fatalf("failed transfer mutated units: source=%v destination=%v", source.Inventory, destination.Inventory)
	}
}
