package battle

import (
	"fmt"
	"math/rand"
)

// NativeCommand0Result is one final-effect candidate resolved by the generic
// command-0 path.  Animation and post-resolution messaging are intentionally
// outside this verified state mutation.
type NativeCommand0Result struct {
	Target *Unit
	NativeCommand0Damage
}

// ExecuteBoundNativeCommand0 uses the state-bound verified resistance table.
// A missing table remains a fail-closed error rather than falling back to the
// legacy magic resistance approximation.
func (s *State) ExecuteBoundNativeCommand0(actor, confirmed *Unit, rng *rand.Rand) ([]NativeCommand0Result, error) {
	if s == nil || len(s.NativeCommandResistances) == 0 {
		return nil, fmt.Errorf("native command 0 resistances unavailable")
	}
	return s.ExecuteNativeCommand0(actor, confirmed, s.NativeCommandResistances, rng)
}

// ExecuteNativeCommand0 joins only the recovered command-0 mechanics:
// record lookup, generic two-stage target selection, one successful MP debit,
// and the 0x1c75e -> 0x1c81f numeric mutation for each final candidate.
// It fails before any mutation if a required raw table entry is absent.
func (s *State) ExecuteNativeCommand0(actor, confirmed *Unit, resistByClass map[int]int, rng *rand.Rand) ([]NativeCommand0Result, error) {
	if s == nil || rng == nil {
		return nil, fmt.Errorf("missing native command state/rng")
	}
	if len(s.NativeCommandBook) != 36 || s.NativeCommandBook[0].ID != 0 {
		return nil, fmt.Errorf("native command 0 record unavailable")
	}
	record := s.NativeCommandBook[0]
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, s.NativeTargetFlags, s.Units)
	if err != nil {
		return nil, err
	}
	// The original table is total for valid runtime class IDs.  Validate every
	// target before 0x1CA89-equivalent MP mutation to keep a missing editable
	// table entry fail-closed rather than making a partial command transaction.
	for _, target := range targets {
		if raw, ok := resistByClass[target.ClassID]; !ok || raw < 0 || raw > 10 {
			return nil, fmt.Errorf("native command 0 missing resistance class=%d", target.ClassID)
		}
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command 0 insufficient MP")
	}
	results := make([]NativeCommand0Result, 0, len(targets))
	for _, target := range targets {
		resolved, err := ApplyNativeCommand0Damage(target, record.Damage, record.Hit, resistByClass[target.ClassID], rng)
		if err != nil {
			return nil, err
		}
		results = append(results, NativeCommand0Result{Target: target, NativeCommand0Damage: resolved})
	}
	return results, nil
}
