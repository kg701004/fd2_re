package battle

import (
	"encoding/binary"
	"fmt"
	"os"
)

// nativeAIDebugf reports which precondition/pipeline made
// nativeAIThreeScorePlan fail-closed, or the raw physical/spell/item scores
// it computed. Silent unless FD2_AI_DEBUG is set -- same opt-in pattern as
// the existing FD2_SHOT_AI hooks in cmd/fd2/main.go. Added 2026-08-15 while
// live-verifying this file's wiring against a real ch01 battle (see
// docs/knowledge-base/11-enemy-ai.md): without it, "native=false" in
// aiStep's own log is ambiguous between "missing provenance" and "genuinely
// no candidate in range", which cost real time to disambiguate once.
func nativeAIDebugf(format string, args ...interface{}) {
	if os.Getenv("FD2_AI_DEBUG") != "" {
		fmt.Fprintf(os.Stderr, "[nativeAIThreeScorePlan] "+format+"\n", args...)
	}
}

// nativeAIThreeScorePlan reproduces 0x14EF0's full three-pipeline decision
// (physical 0x14237, spell 0x1598A, item 0x1567E, then
// SelectNativeAIThreeScoreWinner's winner cascade) for one AI unit's turn.
// It supersedes calling nativeAI14237Plan alone: that function only ever
// tried the physical pipeline, so a unit whose native decision was actually
// to cast a spell was silently treated as "physical found nothing" and fell
// through to the legacy aiTargets approximation instead.
//
// ok=false has the same fail-closed meaning used throughout this package:
// native data was unavailable for some part of the decision, or -- for an
// item winner specifically -- the winning cell had no unit anchor (an
// AoE-style item cast at open ground has no AI target-resolution path yet;
// see the NativeAICommandItem case below) -- the caller must fall back to
// its own normalized planning entirely, not just for movement. When ItemID
// IS resolved to a real target, aiStep executes it through
// ApplyNativeAIItemCommand (see docs/knowledge-base/11-enemy-ai.md's
// 2026-08-15 item-execution-dispatcher note for how that mirrors the
// player-facing applyNativeTargetItem).
//
// ok=true, plan=nil means native authoritatively decided no action is worth
// taking this turn (all three scores stayed below the >=6 gate, or the three
// scores landed in the disassembly-confirmed "no winner" gap -- see
// SelectNativeAIThreeScoreWinner's doc comment).
func (s *State) nativeAIThreeScorePlan(u *Unit) (plan *AIPlan, ok bool) {
	if s == nil || u == nil || !u.HasNativeRecordByte6 || !u.HasNativeRecordByte34 ||
		len(s.NativeItemEffectRows) == 0 || len(s.NativeTerrainMoveCodes) != s.W*s.H ||
		len(s.NativeCommandBook) != NativeCommandRecordCount {
		return nil, false
	}
	actorIndex := -1
	for i, unit := range s.Units {
		if unit == u {
			actorIndex = i
			break
		}
	}
	if actorIndex < 0 {
		nativeAIDebugf("actorIndex not found")
		return nil, false
	}
	costRow, okRow := s.nativeMovementCostRowFor(u)
	if !okRow {
		nativeAIDebugf("nativeMovementCostRowFor failed")
		return nil, false
	}
	baseFlags, err := s.NativeCommandBaseFlags()
	if err != nil {
		nativeAIDebugf("NativeCommandBaseFlags: %v", err)
		return nil, false
	}
	records, err := NativeAIScoringRecords(s.Units)
	if err != nil {
		nativeAIDebugf("NativeAIScoringRecords: %v", err)
		return nil, false
	}
	selector := int(u.NativeRecordByte6)

	physical, err := ScoreNativeAI14237(
		s.W, s.H, records, len(s.Units), actorIndex, selector,
		s.NativeItemEffectRows, baseFlags, s.NativeTerrainMoveCodes, costRow,
	)
	if err != nil {
		nativeAIDebugf("ScoreNativeAI14237: %v", err)
		return nil, false
	}
	physicalPriority := 0
	if physical.HasWinner {
		physicalPriority = physical.Priority
	}

	skip := func(targetIndex int) bool {
		if targetIndex < 0 || targetIndex >= len(s.Units) {
			return false
		}
		return nativeAIPhysicalTerrainPercentApplies(records[targetIndex*nativeRecordSize:])
	}
	spell, err := ScoreNativeAI1598A(
		s.W, s.H, records, len(s.Units), actorIndex, selector, u,
		s.NativeCommandBook, baseFlags, s.NativeTerrainMoveCodes, costRow, skip,
	)
	if err != nil {
		nativeAIDebugf("ScoreNativeAI1598A: %v", err)
		return nil, false
	}

	item, err := ScoreNativeAI1567E(
		s.W, s.H, records, len(s.Units), actorIndex, selector,
		s.NativeItemEffectRows, s.NativeCommandBook, baseFlags,
	)
	if err != nil {
		nativeAIDebugf("ScoreNativeAI1567E: %v", err)
		return nil, false
	}
	nativeAIDebugf("physical=%+v spell=%+v item=%+v", physical, spell, item)

	physicalEquivalentScore := 0
	if physical.HasWinner && physical.TargetIndex >= 0 && physical.TargetIndex < len(s.Units) {
		actorRecord := records[actorIndex*nativeRecordSize:]
		targetRecord := records[physical.TargetIndex*nativeRecordSize:]
		actorAP := int(binary.LittleEndian.Uint16(actorRecord[0x48:0x4a]))
		targetDP := int(binary.LittleEndian.Uint16(targetRecord[0x4a:0x4c]))
		physicalEquivalentScore = actorAP - targetDP
	}

	spellCommandID, spellCommandDamage := 0, 0
	if spell.HasPositiveWinner {
		spellCommandID = spell.PositiveWinner.CommandID
		spellCommandDamage = spell.PositiveWinner.CommandValue
	}

	winner := SelectNativeAIThreeScoreWinner(
		physicalPriority, spell.MaxScore, item.MaxScore,
		u.NativeRecordByte34&0x40 != 0,
		spellCommandID, spellCommandDamage, physicalEquivalentScore,
	)
	nativeAIDebugf("winner=%v physicalPriority=%d spellMax=%d itemMax=%d", winner, physicalPriority, spell.MaxScore, item.MaxScore)

	switch winner {
	case NativeAICommandPhysical:
		if !physical.HasWinner || physical.TargetIndex < 0 || physical.TargetIndex >= len(s.Units) {
			return nil, false
		}
		target := s.Units[physical.TargetIndex]
		if target == nil {
			return nil, false
		}
		p := &AIPlan{U: u, Target: target, SpellID: -1, ItemID: -1, NativeScoredCommands: s.nativeAIPlanScoredCommands(u), NativeSourced: true}
		if u.X != physical.Destination.X || u.Y != physical.Destination.Y {
			p.Path = s.Path(u, physical.Destination.X, physical.Destination.Y)
		}
		return p, true
	case NativeAICommandSpell:
		if !spell.HasPositiveWinner {
			return nil, false
		}
		// spell.PositiveWinner.X/Y is the record+3 destination cell scored
		// against (0x1598a/0x15b77), not necessarily a target's own cell: a
		// SelectionMode==0 (budget-0 flood, self-origin-only) command scores
		// real enemies within record+4's EffectMode radius FROM that
		// destination, so the destination itself is the caster's own cell
		// and UnitAt(X,Y) would resolve to the caster, not a target -- fixed
		// 2026-08-17, see NativeAISpellCandidate's doc comment for the
		// disassembly evidence (0x21548's shared IDs10..12 compositor has no
		// target-selection logic of its own; it consumes exactly this kind
		// of caller-supplied index array). Prefer the already-matched
		// TargetIndices from the winning score group; UnitAt(X,Y) remains a
		// fallback only for legacy/synthetic candidates that never set it.
		var target *Unit
		if len(spell.PositiveWinner.TargetIndices) > 0 {
			index := int(spell.PositiveWinner.TargetIndices[0])
			if index >= 0 && index < len(s.Units) {
				target = s.Units[index]
			}
		}
		if target == nil {
			target = s.UnitAt(spell.PositiveWinner.X, spell.PositiveWinner.Y)
		}
		if target == nil {
			return nil, false
		}
		destination := Cell{X: spell.PositiveWinner.X, Y: spell.PositiveWinner.Y}
		return &AIPlan{
			U: u, Target: target, SpellID: spell.PositiveWinner.CommandID, ItemID: -1,
			Destination:          &destination,
			NativeScoredCommands: s.nativeAIPlanScoredCommands(u), NativeSourced: true,
		}, true
	case NativeAICommandItem:
		if !item.HasPositiveWinner {
			return nil, false
		}
		target := s.UnitAt(item.X, item.Y)
		if target == nil {
			// AoE-style item whose winning cell has no unit anchor (e.g. cast
			// at open ground): ApplyNativeAIItemCommand requires a resolved
			// `confirmed` unit, same as the player's applyNativeTargetItem
			// does. No AI execution path for that shape yet.
			return nil, false
		}
		return &AIPlan{
			U: u, Target: target, SpellID: -1, ItemID: item.ItemID, ItemSlot: item.InventorySlot,
			NativeScoredCommands: s.nativeAIPlanScoredCommands(u), NativeSourced: true,
		}, true
	default:
		return nil, true
	}
}
