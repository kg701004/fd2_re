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

// NativeCommandHitFor is a deliberate remake-only QoL deviation (user
// request): command 9 (咒殺術 — the raw native "50% certain-kill" spell that
// command_labels.json/doc02 mark enemy-only) always hits when the CASTER is
// Own/Ally; an Enemy casting it keeps the original 50 raw native chance from
// spells.json. No other command ID and no target-side camp is affected.
func NativeCommandHitFor(caster *Unit, commandID, rawHit int) int {
	if commandID == 9 && caster != nil && caster.Camp != Enemy {
		return 100
	}
	return rawHit
}

// ExecuteBoundNativeCommand0 uses the state-bound verified resistance table.
// A missing table remains fail-closed rather than falling back to the legacy
// normalized magic approximation.
func (s *State) ExecuteBoundNativeCommand0(actor, confirmed *Unit, rngState uint16, scoredDestination *Cell) ([]NativeCommandDamageResult, uint16, error) {
	if s == nil || len(s.NativeCommandResistances) == 0 {
		return nil, rngState, fmt.Errorf("native command 0 resistances unavailable")
	}
	return s.ExecuteNativeCommandDamage(actor, confirmed, 0, s.NativeCommandResistances, rngState, scoredDestination)
}

// nativeCommandDamageTargets resolves the effect target list for
// ExecuteNativeCommandDamage. SelectionMode==0 (only IDs10..12 in the
// current book) gets a dedicated path: see its doc comment for why the
// generic two-stage NativeCommandEffectTargets is architecturally
// incompatible with a self-origin selection area -- and why it never needs
// scoredDestination (SelectionMode==0 has exactly one possible destination,
// the actor's own cell, so there is no ambiguity to resolve).
func (s *State) nativeCommandDamageTargets(actor, confirmed *Unit, record NativeCommandRecord, flags []byte, scoredDestination *Cell) ([]*Unit, error) {
	if record.SelectionMode != 0 {
		return NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units, scoredDestination)
	}
	return s.nativeSelfOriginCommandTargets(actor, confirmed, record.EffectMode, record.TargetCode, flags)
}

// nativeSelfOriginCommandTargets covers SelectionMode==0 commands (0x21548's
// shared IDs10..12 compositor family, confirmed 2026-08-17 via a headless
// Ghidra probe against the current baseline EXE's FD2Analysis3 project --
// see reference_fd2_live_ghidra_headless_probe memory / doc58's #113
// section). record+3's SelectionMode 0 is a budget-0 flood fill: the only
// cell in range is the caster's own cell. That makes
// NativeCommandEffectTargets's generic 0x1cff0-shaped stage 1 ("is confirmed
// a candidate within the actor's own SelectionMode area, matching camp")
// unsatisfiable by construction for every real target -- no opposing unit
// can ever stand on the caster's own tile. 0x21548's own disassembly has no
// such per-candidate confirmation step at all: the AI dispatcher (0x15311)
// calls 0x14818 exactly once, using the already-chosen destination as the
// origin, and feeds whatever it returns straight into the shared
// 1CA89(MP)/1C75E(damage) core -- there is nothing resembling a
// stage-1-then-stage-2 handoff for this family. This mirrors that: it skips
// straight to EffectMode's area from the ACTOR's own cell (the destination
// SelectionMode==0 always resolves to), matching what nativeAIScoredCommandDestinations
// /nativeAIScoredCommandTargetIndices already validated during scoring.
// confirmed is checked against the resulting list only as a fail-closed
// sanity gate (it must be a real, already-produced target), not because the
// original re-derives target from it.
func (s *State) nativeSelfOriginCommandTargets(actor, confirmed *Unit, effectMode, targetCode int, flags []byte) ([]*Unit, error) {
	rawComplete := nativeTargetRosterRawComplete(s.Units)
	if !nativeTargetActorUsable(actor, rawComplete) || !nativeTargetActorUsable(confirmed, rawComplete) {
		return nil, fmt.Errorf("invalid native command actor/confirmed unit")
	}
	selector, err := nativeActorSelector(actor)
	if err != nil {
		return nil, err
	}
	targets, err := NativeCommandTargets(s.W, s.H, Cell{X: actor.X, Y: actor.Y}, effectMode, targetCode, selector, flags, s.Units)
	if err != nil {
		return nil, err
	}
	for _, target := range targets {
		if target == confirmed {
			return targets, nil
		}
	}
	return nil, fmt.Errorf("confirmed unit is not a native command candidate")
}

// ExecuteNativeCommandDamage covers the byte-for-byte numeric route proven
// for player-dispatched command IDs 0..12. IDs0..8 dispatch directly to
// 0x2A6BD, which runs sub_2B659's MP event and its final-target loop directly
// calls 0x1C75E(targetSlot, commandID). ID9 invokes 0x1CA89 -> 0x1C75E;
// IDs10..12 run their distinct indexed compositor (0x21548) before the same
// state sequence -- their SelectionMode==0 goes through
// nativeSelfOriginCommandTargets instead of the generic two-stage path, see
// that function's doc comment. Other IDs stay fail-closed.
func (s *State) ExecuteNativeCommandDamage(actor, confirmed *Unit, commandID int, resistByClass map[int]int, rngState uint16, scoredDestination *Cell) ([]NativeCommandDamageResult, uint16, error) {
	if s == nil {
		return nil, rngState, fmt.Errorf("missing native command state")
	}
	if commandID < 0 || commandID > 12 || len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[commandID].ID != commandID {
		return nil, rngState, fmt.Errorf("native command damage record unavailable id=%d", commandID)
	}
	record := s.NativeCommandBook[commandID]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, rngState, err
	}
	targets, err := s.nativeCommandDamageTargets(actor, confirmed, record, flags, scoredDestination)
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
		resolved, nextRNG, err := ApplyNativeCommandDamage(target, record.Damage, NativeCommandHitFor(actor, commandID, record.Hit), resistByClass[target.ClassID], rngState)
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
