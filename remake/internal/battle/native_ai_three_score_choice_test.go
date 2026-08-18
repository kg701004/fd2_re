package battle

import "testing"

func TestSelectNativeAIThreeScoreWinnerAllBelowThresholdReturnsNone(t *testing.T) {
	if got := SelectNativeAIThreeScoreWinner(5, 5, 5, false, 0, 0, 0); got != NativeAICommandNone {
		t.Fatalf("got %v, want NativeAICommandNone", got)
	}
}

func TestSelectNativeAIThreeScoreWinnerPhysicalStrictlyHighest(t *testing.T) {
	if got := SelectNativeAIThreeScoreWinner(0x12, 8, 6, false, 0, 0, 0); got != NativeAICommandPhysical {
		t.Fatalf("got %v, want NativeAICommandPhysical", got)
	}
}

func TestSelectNativeAIThreeScoreWinnerPhysicalSpellTieAttackSpellDamageWins(t *testing.T) {
	// physical==spell, physical>item, spellCommandID<0xb, damage>=physicalEquivalent -> spell.
	got := SelectNativeAIThreeScoreWinner(8, 8, 6, false, 3, 20, 10)
	if got != NativeAICommandSpell {
		t.Fatalf("got %v, want NativeAICommandSpell (damage %d >= equivalent %d)", got, 20, 10)
	}
}

func TestSelectNativeAIThreeScoreWinnerPhysicalSpellTieAttackSpellDamageLoses(t *testing.T) {
	// physical==spell, physical>item, spellCommandID<0xb, damage<physicalEquivalent -> physical.
	got := SelectNativeAIThreeScoreWinner(8, 8, 6, false, 3, 5, 10)
	if got != NativeAICommandPhysical {
		t.Fatalf("got %v, want NativeAICommandPhysical (damage %d < equivalent %d)", got, 5, 10)
	}
}

func TestSelectNativeAIThreeScoreWinnerPhysicalSpellTieNonAttackSpellUsesBit(t *testing.T) {
	// spellCommandID>=0xb (heal/buff family): tieBreakBit decides, not damage.
	gotBitClear := SelectNativeAIThreeScoreWinner(8, 8, 6, false, 13, 999, -999)
	if gotBitClear != NativeAICommandSpell {
		t.Fatalf("bit clear: got %v, want NativeAICommandSpell", gotBitClear)
	}
	gotBitSet := SelectNativeAIThreeScoreWinner(8, 8, 6, true, 13, 999, -999)
	if gotBitSet != NativeAICommandPhysical {
		t.Fatalf("bit set: got %v, want NativeAICommandPhysical", gotBitSet)
	}
}

func TestSelectNativeAIThreeScoreWinnerPhysicalItemTieUsesBit(t *testing.T) {
	gotBitClear := SelectNativeAIThreeScoreWinner(8, 6, 8, false, 0, 0, 0)
	if gotBitClear != NativeAICommandItem {
		t.Fatalf("bit clear: got %v, want NativeAICommandItem", gotBitClear)
	}
	gotBitSet := SelectNativeAIThreeScoreWinner(8, 6, 8, true, 0, 0, 0)
	if gotBitSet != NativeAICommandPhysical {
		t.Fatalf("bit set: got %v, want NativeAICommandPhysical", gotBitSet)
	}
}

func TestSelectNativeAIThreeScoreWinnerSpellStrictlyHighest(t *testing.T) {
	if got := SelectNativeAIThreeScoreWinner(6, 10, 8, false, 0, 0, 0); got != NativeAICommandSpell {
		t.Fatalf("got %v, want NativeAICommandSpell", got)
	}
	// spell>physical but spell==item is still a spell win (>= item, not > item).
	if got := SelectNativeAIThreeScoreWinner(6, 10, 10, false, 0, 0, 0); got != NativeAICommandSpell {
		t.Fatalf("spell==item case: got %v, want NativeAICommandSpell", got)
	}
}

func TestSelectNativeAIThreeScoreWinnerItemStrictlyHighest(t *testing.T) {
	if got := SelectNativeAIThreeScoreWinner(6, 8, 10, false, 0, 0, 0); got != NativeAICommandItem {
		t.Fatalf("got %v, want NativeAICommandItem", got)
	}
}

func TestSelectNativeAIThreeScoreWinnerExactThreeWayTieReturnsNone(t *testing.T) {
	// physical==spell==item (all equal, none strictly greater than the
	// others) falls through every branch to the native code's own ambiguous
	// epilogue (0x3a255) without calling any of the three execute dispatch
	// targets -- confirmed from the disassembly, not the same case as the
	// all-below-6 threshold gate (these can be well above 6 and still tie).
	// This corrects an earlier, less careful reading of the tie-break prose
	// that assumed some exact 3-way ties resolve to spell or item.
	got := SelectNativeAIThreeScoreWinner(8, 8, 8, false, 0, 0, 0)
	if got != NativeAICommandNone {
		t.Fatalf("got %v, want NativeAICommandNone for an exact 3-way tie", got)
	}
	got = SelectNativeAIThreeScoreWinner(8, 8, 8, true, 0, 0, 0)
	if got != NativeAICommandNone {
		t.Fatalf("got %v, want NativeAICommandNone for an exact 3-way tie (bit set)", got)
	}
}
