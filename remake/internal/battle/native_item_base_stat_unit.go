package battle

import "fmt"

// ApplyNativeItemBaseStatDeltaToUnit is the editable Unit projection of the
// closed 0x21082 transaction used by item types 8/9/10. It preserves native
// 16-bit wrapping and 0x1b8e7 compact source removal. AP/DP require an
// initialized equipment base; DX is already the independently established raw
// +0x3e field. The caller remains responsible for 0x1145a recomputation.
func ApplyNativeItemBaseStatDeltaToUnit(
	target, source *Unit,
	route NativeItemWordDeltaRoute,
	delta uint16,
	sourceRawSlot int,
) (int, error) {
	verified, ok := NativeItemWordDeltaRouteForType(route.ItemType)
	if !ok || verified != route {
		return 0, fmt.Errorf("native item base-stat route is invalid: %#v", route)
	}
	if target == nil || source == nil {
		return 0, fmt.Errorf("native item base-stat unit is missing")
	}
	compact, err := nativeItemSourceCompactIndex(source, sourceRawSlot)
	if err != nil {
		return 0, err
	}

	var current int
	switch route.BaseStat {
	case NativeItemBaseAP:
		if !target.EquipmentBaseSet {
			return 0, fmt.Errorf("native item AP base provenance is unavailable")
		}
		current = target.BaseAP
	case NativeItemBaseDP:
		if !target.EquipmentBaseSet {
			return 0, fmt.Errorf("native item DP base provenance is unavailable")
		}
		current = target.BaseDP
	case NativeItemBaseDX:
		current = target.DX
	default:
		return 0, fmt.Errorf("native item base stat %q is unsupported", route.BaseStat)
	}

	next := int(int16(uint16(int16(current)) + delta))
	switch route.BaseStat {
	case NativeItemBaseAP:
		target.BaseAP = next
	case NativeItemBaseDP:
		target.BaseDP = next
	case NativeItemBaseDX:
		target.DX = next
		target.BaseHIT, target.BaseEV = next, next
	}
	if !removeNativeCompactInventory(source, compact) {
		return 0, fmt.Errorf("native item source removal failed after preflight")
	}
	return next, nil
}

func nativeItemSourceCompactIndex(source *Unit, sourceRawSlot int) (int, error) {
	if source == nil || sourceRawSlot < 0 || sourceRawSlot >= nativeInventoryCells ||
		len(source.InventorySlots) != nativeInventoryCells ||
		len(source.NativeInventoryFlags) != nativeInventoryCells ||
		source.InventorySlots[sourceRawSlot] == 0xff ||
		source.NativeInventoryFlags[sourceRawSlot]&0x80 != 0 {
		return 0, fmt.Errorf("native item source raw slot %d is unavailable", sourceRawSlot)
	}
	compact := 0
	for slot := 0; slot < sourceRawSlot; slot++ {
		if source.InventorySlots[slot] != 0xff {
			compact++
		}
	}
	if compact >= len(source.Inventory) {
		return 0, fmt.Errorf("native item source compact slot is inconsistent")
	}
	return compact, nil
}
