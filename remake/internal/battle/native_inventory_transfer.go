package battle

import "fmt"

// TransferNativeInventoryItem mirrors the mutation topology proven in the
// 0x2f8ea -> 0x1b8e7 -> 0x1bb8c branch.  The source item is removed from its
// compact inventory slot and inserted into the first empty destination cell;
// 0x1bb8c writes an un-equipped destination cell.  The caller must already
// have applied the native signed-flag eligibility filter (0x2f8ea's list
// builder); this function does not infer equipped state from an item ID.
//
// It is deliberately a raw operation rather than a named church service.
func TransferNativeInventoryItem(source *Unit, sourceIndex int, destination *Unit) error {
	if source == nil || destination == nil {
		return fmt.Errorf("native inventory transfer: missing unit")
	}
	if source == destination {
		return fmt.Errorf("native inventory transfer: source equals destination")
	}
	if sourceIndex < 0 || sourceIndex >= len(source.Inventory) {
		return fmt.Errorf("native inventory transfer: source slot %d out of bounds", sourceIndex)
	}
	itemID := source.Inventory[sourceIndex]
	if itemID < 0 || itemID > 0xff {
		return fmt.Errorf("native inventory transfer: invalid item id %d", itemID)
	}
	// Preflight both fixed-slot layouts before changing either unit.  A full
	// destination is the native failure path and must not consume the source.
	destination.normalizeInventorySlots()
	free := false
	for _, id := range destination.InventorySlots {
		if id == 0xff {
			free = true
			break
		}
	}
	if !free || len(destination.Inventory) >= 8 {
		return fmt.Errorf("native inventory transfer: destination inventory full")
	}
	// Snapshot the compact and source-slot views so an unexpected insertion
	// failure remains atomic even if a future Unit representation changes.
	sourceInventory := append([]int(nil), source.Inventory...)
	sourceEquipped := append([]bool(nil), source.Equipped...)
	sourceSlots := append([]int(nil), source.InventorySlots...)
	sourceFlags := append([]int(nil), source.NativeInventoryFlags...)
	destinationInventory := append([]int(nil), destination.Inventory...)
	destinationEquipped := append([]bool(nil), destination.Equipped...)
	destinationSlots := append([]int(nil), destination.InventorySlots...)
	destinationFlags := append([]int(nil), destination.NativeInventoryFlags...)
	destinationSlot := firstInventoryHole(destination.InventorySlots)
	if !removeNativeCompactInventory(source, sourceIndex) || !destination.AddInventoryItem(itemID, false) {
		source.Inventory, source.Equipped, source.InventorySlots, source.NativeInventoryFlags = sourceInventory, sourceEquipped, sourceSlots, sourceFlags
		destination.Inventory, destination.Equipped, destination.InventorySlots, destination.NativeInventoryFlags = destinationInventory, destinationEquipped, destinationSlots, destinationFlags
		return fmt.Errorf("native inventory transfer: mutation failed")
	}
	if len(destination.NativeInventoryFlags) == nativeInventoryCells && destinationSlot >= 0 {
		destination.NativeInventoryFlags[destinationSlot] = 0
	}
	return nil
}

func firstInventoryHole(slots []int) int {
	for i, item := range slots {
		if item == 0xff {
			return i
		}
	}
	return -1
}

// removeNativeCompactInventory combines the compact editable view with the
// fixed-cell shift performed by native 0x1b8e7.  The latter does not leave a
// hole: cells after the removed slot move left and the tail is marked 0x80.
func removeNativeCompactInventory(u *Unit, compactIndex int) bool {
	if u == nil || compactIndex < 0 || compactIndex >= len(u.Inventory) {
		return false
	}
	u.normalizeInventorySlots()
	seen, slot := 0, -1
	for i, id := range u.InventorySlots {
		if id != 0xff {
			if seen == compactIndex {
				slot = i
				break
			}
			seen++
		}
	}
	if slot < 0 {
		return false
	}
	copy(u.InventorySlots[slot:], u.InventorySlots[slot+1:])
	u.InventorySlots[len(u.InventorySlots)-1] = 0xff
	if len(u.NativeInventoryFlags) == nativeInventoryCells {
		copy(u.NativeInventoryFlags[slot:], u.NativeInventoryFlags[slot+1:])
		u.NativeInventoryFlags[len(u.NativeInventoryFlags)-1] = 0x80
	}
	u.Inventory = append(u.Inventory[:compactIndex], u.Inventory[compactIndex+1:]...)
	if compactIndex < len(u.Equipped) {
		u.Equipped = append(u.Equipped[:compactIndex], u.Equipped[compactIndex+1:]...)
	}
	return true
}
