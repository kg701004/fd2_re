package battle

import (
	"fmt"
	"math/rand"
)

// This file wires up gameplay execution for the four "compound" command IDs
// (32..35) that NativeCompoundCommandPlan (native_command_compound.go) only
// documents as a data-only bridge. Its own doc comment states plainly that
// "target selection, MP debit, transaction/rollback, presentation, and
// runtime mutation remain closed" — so everything below is a remake-level
// functional implementation built from already-verified pieces (per
// docs/knowledge-base/91-worklist.md and 37-spell-effect-figani.md), not an
// assertion of byte-identical native reproduction. Confidence varies by ID:
//   - 32: HIGH — its book Damage/Hit are populated normally (unlike 33..35's
//     zeroed fields), so this just reuses the proven ApplyNativeCommandDamage
//     primitive already used for IDs 0..12. The 0x2111a callee itself is not
//     independently disassembled here.
//   - 33: MEDIUM — the fixed heal amount 800 (0x320) is directly cited in
//     NativeCompoundCommandPlan's case 33 step; the 3 status-marker clears
//     (+0x25/+0x26/+0x27) are NOT reproduced (their gameplay meaning isn't
//     named anywhere in this project's docs) — a known simplification.
//   - 34: HIGH — ApplyNativeRawWordStepAtOffsets's own doc comments name the
//     mutated fields directly ("derived AP +0x48", "derived DP +0x4a"), and
//     the id19 HIT/EV+15 pair is corroborated by a separate worklist entry
//     (RE-ITEM-TYPE12-HIT-EV-22997). Implemented via the existing Unit-level
//     applyBuff helper instead of bridging to the raw-byte-record
//     ApplyNativeCommandModifier API.
//   - 35: MEDIUM — reuses the exact per-offset status-application formula
//     ExecuteNativeCommandApplication already implements for standalone IDs
//     22/26/27, but does NOT call that function directly: it spends its own
//     MP three times (once per sub-ID), which would silently triple-charge
//     against id35's own book MPCost. This file spends id35's MP once and
//     applies the three status effects inline instead.

// ExecuteNativeCommand32 casts 熾天使.
func (s *State) ExecuteNativeCommand32(actor, confirmed *Unit, resistByClass map[int]int, rngState uint16) ([]NativeCommandDamageResult, uint16, error) {
	if s == nil || len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[32].ID != 32 {
		return nil, rngState, fmt.Errorf("native command 32 record unavailable")
	}
	record := s.NativeCommandBook[32]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, rngState, err
	}
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units)
	if err != nil {
		return nil, rngState, err
	}
	for _, target := range targets {
		if raw, ok := resistByClass[target.ClassID]; !ok || raw < 0 || raw > 10 {
			return nil, rngState, fmt.Errorf("native command 32 missing resistance class=%d", target.ClassID)
		}
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, rngState, fmt.Errorf("native command 32 insufficient MP")
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
	actor.Acted = true
	return results, rngState, nil
}

// ExecuteNativeCommand33 casts 風妖精: a fixed 800 HP restore (see file doc).
func (s *State) ExecuteNativeCommand33(actor, confirmed *Unit, rng *rand.Rand) ([]NativeCommandHealResult, error) {
	if s == nil || rng == nil || len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[33].ID != 33 {
		return nil, fmt.Errorf("native command 33 record unavailable")
	}
	record := s.NativeCommandBook[33]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, err
	}
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command 33 insufficient MP")
	}
	const fixedHeal = 0x320 // 800, cited directly in NativeCompoundCommandPlan case 33
	results := make([]NativeCommandHealResult, 0, len(targets))
	for _, target := range targets {
		restore, err := ApplyNativeCommandRestore(target, fixedHeal, rng)
		if err != nil {
			return nil, err
		}
		results = append(results, NativeCommandHealResult{Target: target, Restore: restore})
	}
	actor.Acted = true
	return results, nil
}

// ExecuteNativeCommand34 casts 破壞神: AP+15%, DP+15%, HIT+15, EV+15 in one
// application (see file doc for the offset naming this is based on).
func (s *State) ExecuteNativeCommand34(actor, confirmed *Unit, rng *rand.Rand) ([]*Unit, error) {
	if s == nil || rng == nil || len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[34].ID != 34 {
		return nil, fmt.Errorf("native command 34 record unavailable")
	}
	record := s.NativeCommandBook[34]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, err
	}
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command 34 insufficient MP")
	}
	for _, target := range targets {
		applyBuff(target, rng, 15, 15, 15, 15)
	}
	actor.Acted = true
	return targets, nil
}

// ExecuteNativeCommand35 casts 暗邪鬼: applies the 26(毒擊術)/22(封咒術)/
// 27(麻痺術) status-roll formula to each target at their respective raw
// offsets (0x25/0x27/0x26), spending id35's own MP once rather than calling
// ExecuteNativeCommandApplication three times (see file doc: that would
// triple-charge using the sub-IDs' own MP costs instead).
func (s *State) ExecuteNativeCommand35(actor, confirmed *Unit, rng *rand.Rand) ([]NativeCommandApplicationResult, error) {
	if s == nil || rng == nil || len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[35].ID != 35 {
		return nil, fmt.Errorf("native command 35 record unavailable")
	}
	record := s.NativeCommandBook[35]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, err
	}
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command 35 insufficient MP")
	}
	offsets := [3]int{0x25, 0x27, 0x26} // 26(毒擊術), 22(封咒術), 27(麻痺術)
	results := make([]NativeCommandApplicationResult, 0, len(targets)*3)
	for _, offset := range offsets {
		for _, target := range targets {
			result := NativeCommandApplicationResult{Target: target, Offset: offset}
			duration, _ := target.NativeTransientDuration(offset)
			if duration == 0 && target.ClassID != 0x19 && target.ClassID != 0x1A && rng.Intn(100) < 50 {
				damage := 10*9/10 + rng.Intn(100)*10/1000
				target.ApplyHPDamage(damage)
				result.Applied = true
				result.Damage = damage
				result.Duration = byte(rng.Intn(4) + 2)
				target.SetNativeTransientDuration(offset, result.Duration)
			}
			results = append(results, result)
		}
	}
	actor.Acted = true
	return results, nil
}
