package battle

// NativeAICommandChoice is which of the three 0x14EF0 scoring pipelines won
// for a given AI unit's turn, or that none did.
type NativeAICommandChoice int

const (
	NativeAICommandNone NativeAICommandChoice = iota
	NativeAICommandPhysical
	NativeAICommandSpell
	NativeAICommandItem
)

// SelectNativeAIThreeScoreWinner reproduces 0x14EF0's winner-selection cascade
// exactly as disassembled against the live 新版 reference EXE (linear 0x3a104,
// see docs/data/fd2_ai_14ef0_dispatch_disasm_2026-08-14.txt for the full
// instruction trace this is transcribed from -- read it again, do not rederive
// from the doc11 prose summary, which was an imprecise paraphrase corrected
// 2026-08-15).
//
// physicalPriority/spellScore/itemScore are [0x53C4F]/[0x53C23]/[0x53C33].
// None of the three pipelines runs unless at least one is >=6 (physical's
// slot holds a priority in {0, 8, 0x12}, not a comparable score, but the
// >=6 gate works identically since 0 is the only "no candidate" value).
//
// tieBreakBit is actorRecord[0x34]&0x40 (the high nibble bit, NOT the low
// nibble mode selector already used elsewhere in this package).
//
// spellCommandID/spellCommandDamage/physicalEquivalentScore are only read
// when the cascade reaches the specific "physical==spell, physical>item"
// branch: spellCommandID is the winning spell candidate's raw command ID
// ([0x53C2F]); if it is < 0xb (11), the native code compares the command
// book's Damage field for that command against physicalEquivalentScore
// (actor.AP - target.DP for physical's OWN chosen actor/target pair,
// recomputed independently of 0x14237's own stored score) instead of using
// tieBreakBit -- i.e. commands 0..10 (the direct-damage spell family) get a
// damage-based tie-break, while command IDs >= 11 (heal/buff/status spells)
// fall back to tieBreakBit like the physical/item tie does.
func SelectNativeAIThreeScoreWinner(
	physicalPriority, spellScore, itemScore int,
	tieBreakBit bool,
	spellCommandID, spellCommandDamage, physicalEquivalentScore int,
) NativeAICommandChoice {
	if physicalPriority < 6 && spellScore < 6 && itemScore < 6 {
		return NativeAICommandNone
	}

	if physicalPriority > spellScore && physicalPriority > itemScore {
		return NativeAICommandPhysical
	}

	if physicalPriority == spellScore && physicalPriority > itemScore {
		if spellCommandID < 0xb {
			if spellCommandDamage < physicalEquivalentScore {
				return NativeAICommandPhysical
			}
			return NativeAICommandSpell
		}
		if !tieBreakBit {
			return NativeAICommandSpell
		}
		return NativeAICommandPhysical
	}

	if physicalPriority == itemScore && physicalPriority > spellScore {
		if !tieBreakBit {
			return NativeAICommandItem
		}
		return NativeAICommandPhysical
	}

	if spellScore > physicalPriority && spellScore >= itemScore {
		return NativeAICommandSpell
	}

	if itemScore > physicalPriority && itemScore > spellScore {
		return NativeAICommandItem
	}

	// Reached when none of the above strict/tie conditions hold (e.g.
	// spell > physical but spell < item, and item does not itself clear
	// both) -- the native code falls through to a shared epilogue without
	// calling any of the three execute dispatch targets. Confirmed from the
	// disassembly (0x3a255), not inferred: this is a real "no winner" case
	// distinct from the all-below-6 gate above.
	return NativeAICommandNone
}
