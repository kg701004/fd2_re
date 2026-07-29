package battle

import "testing"

func TestScoreNativePhysicalAttackCandidateRejectsNativeThreshold(t *testing.T) {
	got, ok, err := ScoreNativePhysicalAttackCandidate(NativePhysicalAttackScoreInput{
		ActorWord48:  12,
		TargetWord4A: 10,
		TargetWord40: 1,
	})
	if err != nil || ok || got != (NativePhysicalAttackScore{}) {
		t.Fatalf("score=%+v ok=%v err=%v, want rejected zero result", got, ok, err)
	}
}

func TestScoreNativePhysicalAttackCandidateUsesStrictHPComparison(t *testing.T) {
	got, ok, err := ScoreNativePhysicalAttackCandidate(NativePhysicalAttackScoreInput{
		ActorWord48:    13,
		TargetWord4A:   10,
		TargetWord40:   3,
		RawTargetByte8: 1,
	})
	if err != nil || !ok || got != (NativePhysicalAttackScore{Priority: 8, Score: 3}) {
		t.Fatalf("score=%+v ok=%v err=%v", got, ok, err)
	}

	got, ok, err = ScoreNativePhysicalAttackCandidate(NativePhysicalAttackScoreInput{
		ActorWord48:    14,
		TargetWord4A:   10,
		TargetWord40:   3,
		RawTargetByte8: 1,
	})
	if err != nil || !ok || got != (NativePhysicalAttackScore{Priority: 18, Score: 8}) {
		t.Fatalf("kill score=%+v ok=%v err=%v", got, ok, err)
	}
}

func TestScoreNativePhysicalAttackCandidatePreservesRawAdjustments(t *testing.T) {
	got, ok, err := ScoreNativePhysicalAttackCandidate(NativePhysicalAttackScoreInput{
		ActorWord48:          14,
		ActorWord4A:          5,
		TargetWord48:         8,
		TargetWord4A:         10,
		TargetWord40:         3,
		RawTargetByte8:       0,
		RawHelper1DEBEResult: 1,
	})
	if err != nil || !ok || got != (NativePhysicalAttackScore{Priority: 18, Score: 7}) {
		t.Fatalf("score=%+v ok=%v err=%v", got, ok, err)
	}
}

func TestScoreNativePhysicalAttackCandidateRejectsNonNativeWords(t *testing.T) {
	if _, _, err := ScoreNativePhysicalAttackCandidate(NativePhysicalAttackScoreInput{
		ActorWord48: -1,
	}); err == nil {
		t.Fatal("negative native word accepted")
	}
	if _, _, err := ScoreNativePhysicalAttackCandidate(NativePhysicalAttackScoreInput{
		ActorWord48: 0x10000,
	}); err == nil {
		t.Fatal("oversized native word accepted")
	}
}

func TestSelectNativePhysicalAttackCandidateUsesPriorityThenScoreAndStableTie(t *testing.T) {
	candidates := []NativePhysicalAttackCandidate{
		{
			DestinationX: 2,
			DestinationY: 3,
			TargetIndex:  4,
			Inputs: NativePhysicalAttackScoreInput{
				ActorWord48:    110,
				TargetWord4A:   10,
				TargetWord40:   100,
				RawTargetByte8: 1,
			},
		},
		{
			DestinationX: 5,
			DestinationY: 6,
			TargetIndex:  7,
			Inputs: NativePhysicalAttackScoreInput{
				ActorWord48:    14,
				TargetWord4A:   10,
				TargetWord40:   3,
				RawTargetByte8: 1,
			},
		},
		{
			DestinationX: 8,
			DestinationY: 9,
			TargetIndex:  10,
			Inputs: NativePhysicalAttackScoreInput{
				ActorWord48:    14,
				TargetWord4A:   10,
				TargetWord40:   3,
				RawTargetByte8: 1,
			},
		},
	}
	got, ok, err := SelectNativePhysicalAttackCandidate(candidates)
	if err != nil || !ok {
		t.Fatalf("selection ok=%v err=%v", ok, err)
	}
	if got.Candidate.TargetIndex != 7 || got.Ranking != (NativePhysicalAttackScore{Priority: 18, Score: 8}) {
		t.Fatalf("selection=%+v, want first priority-18 candidate", got)
	}
}

func TestSelectNativePhysicalAttackCandidateFailsClosed(t *testing.T) {
	got, ok, err := SelectNativePhysicalAttackCandidate([]NativePhysicalAttackCandidate{{
		DestinationX: 0x100,
		Inputs: NativePhysicalAttackScoreInput{
			ActorWord48:  10,
			TargetWord4A: 1,
		},
	}})
	if err == nil || ok || got != (NativePhysicalAttackSelection{}) {
		t.Fatalf("selection=%+v ok=%v err=%v, want rejected", got, ok, err)
	}
}
