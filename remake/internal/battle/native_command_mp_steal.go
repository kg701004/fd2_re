package battle

import (
	"fmt"
	"math/rand"
)

// This file implements command ID 36 (MP吸取術/MP steal), a deliberate
// remake-only addition (user request) with no native EXE counterpart --
// unlike every other command in this package, it is not a reverse-engineered
// reproduction of 0x4e516 data. Its book entry (id 36 in assets/spells.json)
// is a hand-authored, editable record; see NativeCommandRecordCount's doc
// comment.

// NativeCommandMPStealResult records one final target of command 36.
type NativeCommandMPStealResult struct {
	Target *Unit
	Hit    bool
	Stolen int // MP actually moved from Target to the caster (0 on a miss)
}

// ExecuteNativeCommandMPSteal casts 36 (MP吸取術): on a successful hit roll
// (record.Hit, same NativeCommandHitFor-eligible mechanism as every other
// command), transfers min(record.Damage, target.MP) MP from each resolved
// target to the caster, clamped so the caster never exceeds its own MaxMP.
// A miss moves nothing. Follows the same shape as ExecuteNativeCommandDamage
// (native_command0.go): resolve targets, spend the caster's own cast cost
// once, then apply the per-target effect.
func (s *State) ExecuteNativeCommandMPSteal(actor, confirmed *Unit, rng *rand.Rand) ([]NativeCommandMPStealResult, error) {
	if s == nil || rng == nil || len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[36].ID != 36 {
		return nil, fmt.Errorf("native command 36 record unavailable")
	}
	record := s.NativeCommandBook[36]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, err
	}
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command 36 insufficient MP")
	}
	results := make([]NativeCommandMPStealResult, 0, len(targets))
	for _, target := range targets {
		result := NativeCommandMPStealResult{Target: target}
		if rollsHitPct(NativeCommandHitFor(actor, 36, record.Hit), rng) {
			amount := record.Damage
			if amount > target.MP {
				amount = target.MP
			}
			room := actor.MaxMP - actor.MP
			if amount > room {
				amount = room
			}
			if amount > 0 {
				target.MP -= amount
				actor.MP += amount
				result.Hit = true
				result.Stolen = amount
			}
		}
		results = append(results, result)
	}
	actor.Acted = true
	return results, nil
}
