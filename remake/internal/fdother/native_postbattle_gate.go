package fdother

// NativePostbattleRoute preserves the address-level branch selected by the
// original postbattle hub gate.  Callee is intentionally an address, not a
// normalized town/shop/church label.
type NativePostbattleRoute struct {
	Selector    byte
	Callee      uint32
	Preparation bool
}

// ResolveNativePostbattleRoute mirrors the proven 0x2cad7/0x2d093 boundary.
// A nonzero 0x526b9 entry selects the preparation path before the hub option
// is read.  For a selectable hub, options 0, 1/3, and 4 dispatch to their
// recovered raw callers; option 2 is the save/confirm→0x318ad preparation
// route.  Unknown indices/options fail closed and no callee is invoked.
func ResolveNativePostbattleRoute(chapterIndex int, gateTable []byte, selector byte) (NativePostbattleRoute, bool) {
	if chapterIndex < 0 || chapterIndex >= len(gateTable) {
		return NativePostbattleRoute{}, false
	}
	if gateTable[chapterIndex] != 0 {
		return NativePostbattleRoute{Selector: selector, Callee: 0x318ad, Preparation: true}, true
	}
	switch selector {
	case 0:
		return NativePostbattleRoute{Selector: selector, Callee: 0x2fc85}, true
	case 1, 3:
		return NativePostbattleRoute{Selector: selector, Callee: 0x2e341}, true
	case 2:
		return NativePostbattleRoute{Selector: selector, Callee: 0x318ad, Preparation: true}, true
	case 4:
		return NativePostbattleRoute{Selector: selector, Callee: 0x3072f}, true
	default:
		return NativePostbattleRoute{}, false
	}
}
