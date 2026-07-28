package fdother

type NativeShopServiceKind string

const (
	NativeShopPurchase NativeShopServiceKind = "purchase"
	NativeShopSell     NativeShopServiceKind = "sell"
	NativeShopEquip    NativeShopServiceKind = "equip"
	NativeShopTransfer NativeShopServiceKind = "inventory_transfer"
)

// NativeShopServiceRoute preserves the resource, callee, and independently
// proven data-mutation semantics chosen by 0x2e341.
type NativeShopServiceRoute struct {
	HubVariant byte
	ResourceID byte
	Selector   byte
	Callee     uint32
	Kind       NativeShopServiceKind
}

// ResolveNativeShopServiceRoute mirrors 0x2e341's proven branch boundary:
// hub variants 3 and 5 select resources 29 and 63; all other variants select
// resource 12.  The confirmed four-entry selector maps to four raw callees.
// It only returns data and never invokes a scene or mutates campaign state.
func ResolveNativeShopServiceRoute(hubVariant, selector byte) (NativeShopServiceRoute, bool) {
	resource := byte(12)
	switch hubVariant {
	case 3:
		resource = 29
	case 5:
		resource = 63
	}
	calleeBySelector := [...]uint32{0x2f0b0, 0x2f642, 0x2f883, 0x2f8ea}
	kindBySelector := [...]NativeShopServiceKind{
		NativeShopPurchase, NativeShopSell, NativeShopEquip, NativeShopTransfer,
	}
	if int(selector) >= len(calleeBySelector) {
		return NativeShopServiceRoute{}, false
	}
	return NativeShopServiceRoute{
		HubVariant: hubVariant, ResourceID: resource, Selector: selector,
		Callee: calleeBySelector[selector], Kind: kindBySelector[selector],
	}, true
}
