package fdother

// NativeHotelServiceRoute preserves the raw selector/resource/callee plan of
// 0x2fc85.  Callees remain address-level and are not given service names.
type NativeHotelServiceRoute struct {
	Selector   byte
	ResourceID byte
	Primary    uint32
	Secondary  uint32
}

// ResolveNativeHotelServiceRoute mirrors the four confirmed 0x2fc85 branches:
// selectors 0,1,2 call 0x2ffa5,0x30012,0x301f4; selector 3 first reads the
// preparation input through 0x19953 and then uses 0x197e5. Resource 13 is
// loaded by the family before the selector loop. This function is data-only.
func ResolveNativeHotelServiceRoute(selector byte) (NativeHotelServiceRoute, bool) {
	route := NativeHotelServiceRoute{Selector: selector, ResourceID: 13}
	switch selector {
	case 0:
		route.Primary = 0x2ffa5
	case 1:
		route.Primary = 0x30012
	case 2:
		route.Primary = 0x301f4
	case 3:
		route.Primary, route.Secondary = 0x19953, 0x197e5
	default:
		return NativeHotelServiceRoute{}, false
	}
	return route, true
}
