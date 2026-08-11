package battle

// NativeCommandMPCostFor is a deliberate remake-only QoL deviation (user
// request): Own/Ally units pay a flat 1 MP for any command that costs more
// than 0, regardless of its native record cost; Enemy units always pay the
// original book cost. This intentionally reuses the single shared
// NativeCommandRecord book (see command_labels.json: 咒殺術/id 9 sits in the
// same 0..35 table as player-only 破龍擊/id 24) rather than forking data, so
// both NativeCommandAvailable and SpendNativeCommandMP must call this same
// helper to stay consistent with each other.
func NativeCommandMPCostFor(unit *Unit, rawCost int) int {
	if unit != nil && unit.Camp != Enemy && rawCost > 0 {
		return 1
	}
	return rawCost
}

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
	if unit == nil || cost < 0 || cost > 0xff {
		return false
	}
	effective := NativeCommandMPCostFor(unit, cost)
	if unit.MP < effective {
		return false
	}
	unit.MP -= effective
	return true
}
