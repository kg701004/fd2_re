package battle

import (
	"fmt"
	"math/rand"
)

// NativeCommand25Result is one final-effect target in the recovered ID25
// route. Cleared reports the direct unit+5 bit0x80 mutation performed by
// 0x22C04; it does not assign a gameplay name to the command.
type NativeCommand25Result struct {
	Target  *Unit
	Cleared bool
}

// ExecuteNativeCommand25 mirrors the verified state portion of
// 0x22C04: generic 0x1CFF0 two-stage targets, record-25 MP debit, then clear
// unit+5 bit0x80 only when it was already set. The wrapper's successful
// command completion still consumes the actor's action after the effect.
// Renderer, message feedback and UI remain outside this fail-closed slice.
//
// rng is only consumed by the [0x53EC8] experience accumulator (see
// native_command_exp.go) when at least one target's acted bit was actually
// cleared; it may be nil for any call that is guaranteed not to award
// experience (e.g. actor camp Enemy, or no target ends up Cleared), matching
// the existing test fixtures that pass nil here.
func (s *State) ExecuteNativeCommand25(actor, confirmed *Unit, scoredDestination *Cell, rng *rand.Rand) ([]NativeCommand25Result, error) {
	const commandID = 25
	if s == nil || len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[commandID].ID != commandID {
		return nil, fmt.Errorf("native command 25 record unavailable")
	}
	record := s.NativeCommandBook[commandID]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, err
	}
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units, scoredDestination)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command 25 insufficient MP")
	}
	results := make([]NativeCommand25Result, 0, len(targets))
	clearedTargets := make([]*Unit, 0, len(targets))
	for _, target := range targets {
		cleared := target.Acted
		if cleared {
			target.Acted = false
			clearedTargets = append(clearedTargets, target)
		}
		results = append(results, NativeCommand25Result{Target: target, Cleared: cleared})
	}
	// [0x53EC8] write point 0x22C04 (doc13 §7's noted increment beyond doc27
	// §5.1's six-entry list): levelFactor(target)*8 per cleared target. Only
	// reached -- and only touches rng -- when clearedTargets is non-empty.
	if len(clearedTargets) > 0 && rng != nil {
		s.awardNativeCommandExp(actor, clearedTargets, 8, rng)
	}
	// 0x18D8C sets the invoking actor's completion bit only after the handler
	// returns success. It is independent from the target bit that ID25 clears.
	actor.Acted = true
	return results, nil
}
