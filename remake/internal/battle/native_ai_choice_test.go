package battle

import "testing"

func TestSelectNativeAISpellCandidateUsesScoreThenRawCommandValue(t *testing.T) {
	got, ok := SelectNativeAISpellCandidate([]NativeAISpellCandidate{
		{CommandID: 17, CommandValue: 4, X: 1, Y: 2, Score: 6},
		{CommandID: 18, CommandValue: 7, X: 3, Y: 4, Score: 6},
		{CommandID: 19, CommandValue: 99, X: 5, Y: 6, Score: 5},
	})
	if !ok || got.CommandID != 18 || got.X != 3 || got.Y != 4 {
		t.Fatalf("choice=%+v ok=%v", got, ok)
	}
	got, ok = SelectNativeAISpellCandidate([]NativeAISpellCandidate{
		{CommandID: 17, CommandValue: 7, Score: 6},
		{CommandID: 18, CommandValue: 7, Score: 6},
	})
	if !ok || got.CommandID != 17 {
		t.Fatalf("exact tie should keep first candidate: %+v", got)
	}
}

func TestSelectNativeAISpellCandidateEmptyIsFailClosed(t *testing.T) {
	if _, ok := SelectNativeAISpellCandidate(nil); ok {
		t.Fatal("empty native AI candidate list selected a command")
	}
}
