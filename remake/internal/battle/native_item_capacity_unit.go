package battle

import "fmt"

// ApplyNativeItemCapacityToUnit projects the closed type17/18/19 0x21082
// transaction onto editable Unit fields. Max HP/MP use native signed-word
// wrapping while leaving current HP/MP unchanged. MV uses the low byte of the
// +0x3b word add and preserves EXP exactly, matching the caller save/restore.
func ApplyNativeItemCapacityToUnit(
	target, source *Unit,
	route NativeItemCapacityStepRoute,
	sourceRawSlot int,
) (int, error) {
	verified, ok := NativeItemCapacityStepRouteForType(route.ItemType, route.Amount)
	if !ok || verified != route {
		return 0, fmt.Errorf("native item capacity route is invalid: %#v", route)
	}
	if target == nil || source == nil {
		return 0, fmt.Errorf("native item capacity unit is missing")
	}
	compact, err := nativeItemSourceCompactIndex(source, sourceRawSlot)
	if err != nil {
		return 0, err
	}

	var next int
	switch route.Stat {
	case NativeItemMaxHP:
		next = int(int16(uint16(int16(target.MaxHP)) + route.Amount))
	case NativeItemMaxMP:
		next = int(int16(uint16(int16(target.MaxMP)) + route.Amount))
	case NativeItemMV:
		if target.MV < 0 || target.MV > 0xff {
			return 0, fmt.Errorf("native item MV byte is out of range")
		}
		next = int(byte(target.MV) + byte(route.Amount))
	default:
		return 0, fmt.Errorf("native item capacity stat %q is unsupported", route.Stat)
	}

	switch route.Stat {
	case NativeItemMaxHP:
		target.MaxHP = next
	case NativeItemMaxMP:
		target.MaxMP = next
	case NativeItemMV:
		target.MV = next
		if target.EquipmentBaseSet {
			target.BaseMV = next
		}
	}
	if !removeNativeCompactInventory(source, compact) {
		return 0, fmt.Errorf("native item source removal failed after preflight")
	}
	return next, nil
}
