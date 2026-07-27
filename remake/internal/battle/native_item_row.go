package battle

import "fmt"

const (
	// NativeItemEffectTableBase is the linear address used by 0x4e56c after
	// relocation into the EXE data image.  The helper below returns an offset
	// relative to that table; it does not assign names to the row fields.
	NativeItemEffectTableBase = 0x602ad
	NativeItemEffectRowSize   = 0x17
)

// NativeItemBaseStat identifies the three persistent base words consumed by
// 0x1145a. Their meanings are closed by the 215-row AP/HIT/DP/EV cross-check,
// not inferred from presentation codes.
type NativeItemBaseStat string

const (
	NativeItemBaseAP NativeItemBaseStat = "ap"
	NativeItemBaseDP NativeItemBaseStat = "dp"
	NativeItemBaseDX NativeItemBaseStat = "dx"
)

// NativeItemWordDeltaRoute is the raw dispatch contract for item types 8, 9
// and 0xa in 0x20c6f.  0x21082 receives the item row's +0xe word as delta,
// permanently adds it to the target record's base AP/DP/DX word, and receives
// a separate presentation selector whose meaning remains opaque.
type NativeItemWordDeltaRoute struct {
	ItemType         int
	BaseStat         NativeItemBaseStat
	FieldOffset      int
	PresentationCode int
}

func NativeItemWordDeltaRouteForType(itemType int) (NativeItemWordDeltaRoute, bool) {
	switch itemType {
	case 8:
		return NativeItemWordDeltaRoute{ItemType: itemType, BaseStat: NativeItemBaseAP, FieldOffset: 0x37, PresentationCode: 0x11}, true
	case 9:
		return NativeItemWordDeltaRoute{ItemType: itemType, BaseStat: NativeItemBaseDP, FieldOffset: 0x39, PresentationCode: 0x12}, true
	case 0xa:
		return NativeItemWordDeltaRoute{ItemType: itemType, BaseStat: NativeItemBaseDX, FieldOffset: 0x3e, PresentationCode: 0x13}, true
	default:
		return NativeItemWordDeltaRoute{}, false
	}
}

// NativeItemEffectRowOffset reproduces 0x4e56c(item): item rows are selected
// with a 23-byte stride from the table base.  The native routine has no bounds
// check, so this adapter validates the byte-sized selector and returns only
// the proven table-relative offset.
func NativeItemEffectRowOffset(item int) (int, error) {
	if item < 0 || item > 0xff {
		return 0, fmt.Errorf("native item selector %d is out of bounds", item)
	}
	return item * NativeItemEffectRowSize, nil
}
