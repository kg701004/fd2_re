// native_command_exp.go — the [0x53EC8] experience accumulator shared by the
// native raw-ABI command family (IDs 17..27 today; see
// docs/knowledge-base/13-battle-menu-system.md "native commands 20..27
// 殘留缺口收斂" §7 and docs/knowledge-base/27-combat-rules-and-validation-checklist.md
// §5.1 for the underlying reverse-engineering evidence).
//
// The original does, per action: 0x117e7 zeroes DAT_00053ec8 before the
// handler runs; each successful per-target effect inside that handler adds
// `levelFactor(target) * commandMultiplier` to it; the accumulator is
// clamp(0,99)'d; then 0x1e292 adds it onto the acting unit's persistent
// experience byte (+0x3c), rolling levels at the fixed 100-per-level
// threshold and recomputing derived stats via 0x1b750 on every level gained.
//
// This engine already has that exact threshold-100 / recompute-on-level-up
// pipeline for the legacy CastArea spell path: growth.go's State.GainExp.
// Rather than fork a second persistent-experience field for the native raw
// path, this reuses the same Unit.Exp accumulator and the same GainExp
// leveling/growth logic -- the two paths are simply two different sources
// feeding the one persistent counter, which is the same simplification this
// codebase already made for command 23 in the legacy CastArea case (see
// magic.go's TeleportExp comment).
package battle

import "math/rand"

// nativeCommandExpLevelFactor mirrors the target level factor shared by every
// documented [0x53EC8] write point: the target's own level, plus 0x1e (30)
// when its class falls in (8, 0x19) i.e. 9..24 inclusive (doc13 §7 / doc27
// §5.1.A: "target.+0x21(等級), 若 target.+0x20(class) 落在 (8,0x19) 則 +0x1e").
func nativeCommandExpLevelFactor(target *Unit) int {
	if target == nil {
		return 0
	}
	factor := target.Lv
	if target.ClassID > 8 && target.ClassID < 0x19 {
		factor += 0x1e
	}
	return factor
}

// awardNativeCommandExp accumulates levelFactor(target)*multiplier for every
// supplied (already-successful) target, clamps the sum to 99 exactly as
// 0x117e7/0x1e292 clamp DAT_00053ec8, and -- only if that clamped sum is
// positive -- feeds it into the actor's persistent experience via the
// existing GainExp threshold/level-up/growth pipeline. A nil/empty target
// list or a non-positive sum is a deliberate no-op: it must never itself
// consume an RNG draw, so it cannot perturb callers (including existing
// regression tests) that don't expect one when nothing was actually gained.
func (s *State) awardNativeCommandExp(actor *Unit, targets []*Unit, multiplier int, rng *rand.Rand) []LevelUpEvent {
	if s == nil || actor == nil || multiplier <= 0 || len(targets) == 0 {
		return nil
	}
	accum := 0
	for _, target := range targets {
		accum += nativeCommandExpLevelFactor(target) * multiplier
	}
	if accum > 99 {
		accum = 99
	}
	if accum <= 0 {
		return nil
	}
	return s.GainExp(actor, float64(accum), rng)
}
