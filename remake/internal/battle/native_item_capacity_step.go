package battle

import (
	"encoding/binary"
	"fmt"
)

type NativeItemCapacityStat string

const (
	NativeItemMaxHP NativeItemCapacityStat = "max_hp"
	NativeItemMaxMP NativeItemCapacityStat = "max_mp"
	NativeItemMV    NativeItemCapacityStat = "mv"
)

// NativeItemCapacityStepRoute closes type 17–19 around 0x21082. All three
// consume the source slot. Type 19 uses a word add at +0x3b but its caller
// restores byte +0x3c, so only MV changes and EXP is preserved.
type NativeItemCapacityStepRoute struct {
	ItemType         byte
	Stat             NativeItemCapacityStat
	FieldOffset      int
	Amount           uint16
	PresentationCode int
	ConsumesSource   bool
}

func NativeItemCapacityStepRouteForType(itemType byte, amount uint16) (NativeItemCapacityStepRoute, bool) {
	switch itemType {
	case 17:
		return NativeItemCapacityStepRoute{
			ItemType: itemType, Stat: NativeItemMaxHP, FieldOffset: 0x42,
			Amount: amount, PresentationCode: 13, ConsumesSource: true,
		}, true
	case 18:
		return NativeItemCapacityStepRoute{
			ItemType: itemType, Stat: NativeItemMaxMP, FieldOffset: 0x46,
			Amount: amount, PresentationCode: 13, ConsumesSource: true,
		}, true
	case 19:
		return NativeItemCapacityStepRoute{
			ItemType: itemType, Stat: NativeItemMV, FieldOffset: 0x3b,
			Amount: amount, PresentationCode: 19, ConsumesSource: true,
		}, true
	default:
		return NativeItemCapacityStepRoute{}, false
	}
}

func ApplyNativeItemCapacityStep(
	records []byte,
	targetUnit int,
	route NativeItemCapacityStepRoute,
	sourceUnit, sourceSlot int,
) (uint16, error) {
	verified, ok := NativeItemCapacityStepRouteForType(route.ItemType, route.Amount)
	if !ok || verified != route {
		return 0, fmt.Errorf("native item capacity route is invalid: %#v", route)
	}
	targetBase := targetUnit * nativeRecordSize
	if targetUnit < 0 || targetBase < 0 || targetBase+nativeRecordSize > len(records) {
		return 0, recordBoundsError(targetUnit)
	}
	preservedEXP := records[targetBase+0x3c]
	if _, err := ApplyNativeWordDeltaAndRemove(
		records, targetUnit, route.FieldOffset, int(route.Amount), sourceUnit, sourceSlot,
	); err != nil {
		return 0, err
	}
	if route.Stat == NativeItemMV {
		records[targetBase+0x3c] = preservedEXP
		return uint16(records[targetBase+0x3b]), nil
	}
	return binary.LittleEndian.Uint16(records[targetBase+route.FieldOffset:]), nil
}
