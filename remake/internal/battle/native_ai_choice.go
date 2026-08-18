package battle

// NativeAISpellCandidate is the already-resolved raw candidate tuple consumed
// by 0x1598a after command availability and target resolution. CommandValue
// is the command record word at +0; X/Y are caller-provided raw coordinates.
//
// TargetIndices is the same record-index array 0x15b77 scored this candidate
// against (see NativeAIScoredCommandCandidateGroup.TargetIndices). It is
// needed because X/Y is the record+3 destination cell, not necessarily a
// target's own cell: 0x21548's disassembly (2026-08-17, FD2Analysis3
// Ghidra project, confirmed via a fresh headless probe against the current
// baseline EXE) shows commands whose record+3 SelectionMode resolves to 0
// (budget-0 flood fill = the caster's own cell only) score real enemies via
// record+4's EffectMode radius FROM that destination, not AT it -- for
// those, X/Y is the caster's own position, and looking up "the unit
// standing at X/Y" finds the caster, not a target. Confirmed IDs 10/11/12
// (0x21527/0x2185f/0x21a9e -> shared 0x21548 compositor) do exactly this;
// their execution tail loops a caller-supplied target-index array through
// the same 1CA89/1C75E core every other command ID uses, so 0x21548 itself
// has no target-selection logic of its own -- the array must come from the
// same 0x14818 geometry already captured in TargetIndices here.
type NativeAISpellCandidate struct {
	CommandID     int
	CommandValue  int
	X             int
	Y             int
	Score         int
	TargetIndices []byte
}

// SelectNativeAISpellCandidate preserves 0x1598a's strict score comparison:
// greater score wins; equal score compares raw command +0; an exact tie keeps
// the first candidate. It does not perform MP, target, status, or UI work.
func SelectNativeAISpellCandidate(candidates []NativeAISpellCandidate) (NativeAISpellCandidate, bool) {
	if len(candidates) == 0 {
		return NativeAISpellCandidate{}, false
	}
	best := candidates[0]
	for _, candidate := range candidates[1:] {
		if candidate.Score > best.Score || (candidate.Score == best.Score && candidate.CommandValue > best.CommandValue) {
			best = candidate
		}
	}
	return best, true
}
