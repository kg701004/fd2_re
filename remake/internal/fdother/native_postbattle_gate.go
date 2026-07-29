package fdother

// NativePostbattleRoute preserves the address-level branch selected by the
// original postbattle hub gate.  Callee is intentionally an address, not a
// normalized town/shop/church label.
type NativePostbattleRoute struct {
	Selector          byte
	Callee            uint32
	Preparation       bool
	DirectPreparation bool
}

// NativePostbattleOutcome preserves whether 0x2cad7 loops internally or
// returns a raw value to its caller.  ReturnValue is meaningful only when
// Repeat is false; this layer does not name raw 0/1 as a scene or campaign
// outcome.
type NativePostbattleOutcome struct {
	Repeat      bool
	ReturnValue int
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
		return NativePostbattleRoute{
			Selector:          selector,
			Callee:            0x318ad,
			Preparation:       true,
			DirectPreparation: true,
		}, true
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

// ResolveNativePostbattleOutcome mirrors 0x2cccc..0x2ccff and
// 0x2cf3d..0x2cf6a after the selected raw callee returns.
//
// A zero callee result repeats the current direct-preparation prompt or town
// hub.  A nonzero result from direct preparation, or from town selector 2,
// returns raw zero.  A nonzero result from the other town selectors returns
// raw one.  The outer 0x25de5 caller owns the meaning of those raw values.
func ResolveNativePostbattleOutcome(
	route NativePostbattleRoute,
	calleeResult int,
) (NativePostbattleOutcome, bool) {
	if route.Callee == 0 {
		return NativePostbattleOutcome{}, false
	}
	if route.DirectPreparation {
		if route.Callee != 0x318ad || !route.Preparation {
			return NativePostbattleOutcome{}, false
		}
	} else {
		switch route.Selector {
		case 0:
			if route.Callee != 0x2fc85 || route.Preparation {
				return NativePostbattleOutcome{}, false
			}
		case 1, 3:
			if route.Callee != 0x2e341 || route.Preparation {
				return NativePostbattleOutcome{}, false
			}
		case 2:
			if route.Callee != 0x318ad || !route.Preparation {
				return NativePostbattleOutcome{}, false
			}
		case 4:
			if route.Callee != 0x3072f || route.Preparation {
				return NativePostbattleOutcome{}, false
			}
		default:
			return NativePostbattleOutcome{}, false
		}
	}
	if calleeResult == 0 {
		return NativePostbattleOutcome{Repeat: true}, true
	}
	if route.DirectPreparation || route.Selector == 2 {
		return NativePostbattleOutcome{ReturnValue: 0}, true
	}
	return NativePostbattleOutcome{ReturnValue: 1}, true
}
