package battle

import (
	"fmt"
)

// NativeCommandDamageResult is one final-effect candidate resolved by the
// verified numeric damage path. Animation and post-resolution messaging are
// intentionally outside this state mutation.
type NativeCommandDamageResult struct {
	Target *Unit
	NativeCommandDamage
}

// ExecuteBoundNativeCommand0 uses the state-bound verified resistance table.
// A missing table remains fail-closed rather than falling back to the legacy
// normalized magic approximation.
func (s *State) ExecuteBoundNativeCommand0(actor, confirmed *Unit, rngState uint16) ([]NativeCommandDamageResult, uint16, error) {
	if s == nil || len(s.NativeCommandResistances) == 0 {
		return nil, rngState, fmt.Errorf("native command 0 resistances unavailable")
	}
	return s.ExecuteNativeCommandDamage(actor, confirmed, 0, s.NativeCommandResistances, rngState)
}

// ExecuteNativeCommandDamage covers the byte-for-byte numeric route proven
// for player-dispatched command IDs 0..12. IDs0..8 dispatch directly to
// 0x2A6BD, which runs sub_2B659's MP event and its final-target loop directly
// calls 0x1C75E(targetSlot, commandID). ID9 invokes 0x1CA89 -> 0x1C75E;
// IDs10..12 run their distinct indexed compositor (0x21548) before the same
// state sequence. Other IDs stay fail-closed.
func (s *State) ExecuteNativeCommandDamage(actor, confirmed *Unit, commandID int, resistByClass map[int]int, rngState uint16) ([]NativeCommandDamageResult, uint16, error) {
	if s == nil {
		return nil, rngState, fmt.Errorf("missing native command state")
	}
	if commandID < 0 || commandID > 12 || len(s.NativeCommandBook) != 36 || s.NativeCommandBook[commandID].ID != commandID {
		return nil, rngState, fmt.Errorf("native command damage record unavailable id=%d", commandID)
	}
	record := s.NativeCommandBook[commandID]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, rngState, err
	}
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units)
	if err != nil {
		return nil, rngState, err
	}
	// The original table is total for valid runtime class IDs.  Validate every
	// target before 0x1CA89-equivalent MP mutation to keep a missing editable
	// table entry fail-closed rather than making a partial command transaction.
	for _, target := range targets {
		if raw, ok := resistByClass[target.ClassID]; !ok || raw < 0 || raw > 10 {
			return nil, rngState, fmt.Errorf("native command damage missing resistance class=%d", target.ClassID)
		}
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, rngState, fmt.Errorf("native command damage insufficient MP")
	}
	results := make([]NativeCommandDamageResult, 0, len(targets))
	for _, target := range targets {
		resolved, nextRNG, err := ApplyNativeCommandDamage(target, record.Damage, record.Hit, resistByClass[target.ClassID], rngState)
		if err != nil {
			return nil, rngState, err
		}
		rngState = nextRNG
		results = append(results, NativeCommandDamageResult{Target: target, NativeCommandDamage: resolved})
	}
	// 0x18D8C calls 0x13512 only after 0x1CFF0 reports success; 0x13512 is
	// the direct unit+5 bit0x80 writer projected as Unit.Acted.
	actor.Acted = true
	return results, rngState, nil
}
