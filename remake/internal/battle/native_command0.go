package battle

import (
	"fmt"
	"math/rand"
)

// NativeCommandDamageResult is one final-effect candidate resolved by the
// verified numeric damage path. Animation and post-resolution messaging are
// intentionally outside this state mutation.
type NativeCommandDamageResult struct {
	Target *Unit
	NativeCommandDamage
}

// ExecuteNativeCommandDamage covers the byte-for-byte numeric route proven
// for player-dispatched command IDs 9..12. ID9 directly invokes
// 0x1CA89 -> 0x1C75E; IDs10..12 run their distinct indexed compositor
// (0x21548) before the same state sequence. IDs0..8 instead dispatch directly
// to 0x2A6BD, whose gameplay writer has not been recovered, so they stay
// fail-closed.
func (s *State) ExecuteNativeCommandDamage(actor, confirmed *Unit, commandID int, resistByClass map[int]int, rng *rand.Rand) ([]NativeCommandDamageResult, error) {
	if s == nil || rng == nil {
		return nil, fmt.Errorf("missing native command state/rng")
	}
	if commandID < 9 || commandID > 12 || len(s.NativeCommandBook) != 36 || s.NativeCommandBook[commandID].ID != commandID {
		return nil, fmt.Errorf("native command damage record unavailable id=%d", commandID)
	}
	record := s.NativeCommandBook[commandID]
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, s.NativeTargetFlags, s.Units)
	if err != nil {
		return nil, err
	}
	// The original table is total for valid runtime class IDs.  Validate every
	// target before 0x1CA89-equivalent MP mutation to keep a missing editable
	// table entry fail-closed rather than making a partial command transaction.
	for _, target := range targets {
		if raw, ok := resistByClass[target.ClassID]; !ok || raw < 0 || raw > 10 {
			return nil, fmt.Errorf("native command damage missing resistance class=%d", target.ClassID)
		}
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command damage insufficient MP")
	}
	results := make([]NativeCommandDamageResult, 0, len(targets))
	for _, target := range targets {
		resolved, err := ApplyNativeCommandDamage(target, record.Damage, record.Hit, resistByClass[target.ClassID], rng)
		if err != nil {
			return nil, err
		}
		results = append(results, NativeCommandDamageResult{Target: target, NativeCommandDamage: resolved})
	}
	// 0x18D8C calls 0x13512 only after 0x1CFF0 reports success; 0x13512 is
	// the direct unit+5 bit0x80 writer projected as Unit.Acted.
	actor.Acted = true
	return results, nil
}
