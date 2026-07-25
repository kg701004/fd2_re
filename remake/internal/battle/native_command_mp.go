package battle

// SpendNativeCommandMP mirrors the successful post-confirm portion of
// 0x1CA89: subtract command record byte+5 from runtime unit+0x44 (current
// MP).  The native selector has already checked current MP >= byte+5 before
// reaching this helper; return false and leave state unchanged if that
// precondition is absent in the remake caller.
//
// This intentionally takes the raw command-record cost, not a legacy Spell:
// the two tables are byte-identical only for the verified IDs 0..35, while
// their normalized gameplay semantics are not interchangeable.
func SpendNativeCommandMP(unit *Unit, cost int) bool {
	if unit == nil || cost < 0 || cost > 0xff || unit.MP < cost {
		return false
	}
	unit.MP -= cost
	return true
}
