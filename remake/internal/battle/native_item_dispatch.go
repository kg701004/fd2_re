package battle

// NativeItemEffectRoute is the raw call-topology result of 0x20c6f.  The
// fields intentionally retain addresses and integer arguments instead of
// naming an item type as potion, status, damage, or equipment behavior.
type NativeItemEffectRoute struct {
	ItemType  byte
	Word      uint16 // item row +0x0e, passed to callees that consume it
	Primary   uint32
	Secondary uint32
	Arg2      int
	Arg5      int
	Arg7      int
}

// NativeItemEffectRouteForType reproduces the verified dispatch table in
// 0x20c6f without executing any callee or mutating runtime state.  A false
// result means the type is not covered by the recovered table.
func NativeItemEffectRouteForType(itemType byte, word uint16) (NativeItemEffectRoute, bool) {
	route := NativeItemEffectRoute{ItemType: itemType, Word: word}
	switch itemType {
	case 5, 13:
		route.Primary = 0x211a4
	case 6:
		route.Primary, route.Arg2, route.Arg5 = 0x22af6, 20, 37
	case 7:
		route.Primary, route.Arg2, route.Arg5 = 0x22af6, 21, 38
	case 8:
		route.Primary, route.Arg2, route.Arg7 = 0x21082, 55, 17
	case 9:
		route.Primary, route.Arg2, route.Arg7 = 0x21082, 57, 18
	case 10:
		route.Primary, route.Arg2, route.Arg7 = 0x21082, 62, 19
	case 11:
		route.Primary, route.Secondary, route.Arg2 = 0x1c4cc, 0x1c2da, 13
	case 12:
		route.Primary = 0x22997
	case 14:
		route.Primary, route.Arg2, route.Arg5 = 0x22d1b, 27, 38
	case 15:
		route.Primary = 0x22866
	case 16:
		route.Primary = 0x22721
	case 17:
		route.Primary, route.Arg2, route.Arg7 = 0x21082, 66, 13
	case 18:
		route.Primary, route.Arg2, route.Arg7 = 0x21082, 70, 13
	case 19:
		route.Primary, route.Arg2, route.Arg7 = 0x21082, 59, 19
	case 20, 24:
		route.Primary, route.Secondary = 0x1c4cc, 0x1cd17
	case 21:
		route.Primary = 0x2111a
	case 22:
		route.Primary, route.Arg2, route.Arg5 = 0x22d1b, 22, 39
	case 23:
		route.Primary = 0x2218a
	default:
		return NativeItemEffectRoute{}, false
	}
	return route, true
}
