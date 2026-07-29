package fdother

import "testing"

func TestFindNativePhaseDispatchCandidatesUsesRawGates(t *testing.T) {
	raw := make([]byte, 3*0x50)
	raw[6] = 1
	raw[0x50+6] = 1
	raw[0x50+5] = 0x80
	raw[2*0x50+6] = 1
	raw[2*0x50+0x26] = 1
	got, err := FindNativePhaseDispatchCandidates(raw, 3)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].UnitIndex != 0 || got[0].SelectorArg != 1 {
		t.Fatalf("candidates = %#v", got)
	}
}

func TestFindNativePhaseDispatchCandidatesRejectsTruncatedInput(t *testing.T) {
	if _, err := FindNativePhaseDispatchCandidates(make([]byte, 0x50-1), 1); err == nil {
		t.Fatal("expected truncated raw records to fail closed")
	}
}

func TestFindNativePhaseDispatchCandidatesAllowsZeroCountWithoutStorage(t *testing.T) {
	got, err := FindNativePhaseDispatchCandidates(nil, 0)
	if err != nil || len(got) != 0 {
		t.Fatalf("zero-count result = %#v, %v", got, err)
	}
}

func TestPlanNativePhaseUnitScansPreservesTwoZeroPassesAndSignedGate(t *testing.T) {
	raw := make([]byte, 5*0x50)
	raw[6] = 1
	raw[0x50+6] = 0
	raw[2*0x50+6] = 0
	raw[3*0x50+6] = 0
	raw[3*0x50+5] = 1
	raw[4*0x50+6] = 0
	raw[4*0x50+0x26] = 1
	scores := make([]NativePhasePreselectionScores, 5)
	scores[1] = NativePhasePreselectionScores{
		SpellCandidateScore53C23: 5, ItemCommandScore53C33: 6,
	}
	scores[2] = NativePhasePreselectionScores{
		SpellCandidateScore53C23: -1, ItemCommandScore53C33: 5,
	}

	plan, err := PlanNativePhaseUnitScans(raw, 5, scores)
	if err != nil {
		t.Fatal(err)
	}
	if len(plan.SelectorOne) != 1 ||
		plan.SelectorOne[0].UnitIndex != 0 ||
		plan.SelectorOne[0].SelectorArg != 1 {
		t.Fatalf("selector-one pass = %#v", plan.SelectorOne)
	}
	if len(plan.ZeroPreselection) != 2 ||
		plan.ZeroPreselection[0].UnitIndex != 1 ||
		!plan.ZeroPreselection[0].RunUnitAction ||
		plan.ZeroPreselection[1].UnitIndex != 2 ||
		plan.ZeroPreselection[1].RunUnitAction {
		t.Fatalf("zero preselection = %#v", plan.ZeroPreselection)
	}
	if len(plan.ZeroSecondPass) != 2 ||
		plan.ZeroSecondPass[0].UnitIndex != 1 ||
		plan.ZeroSecondPass[1].UnitIndex != 2 {
		t.Fatalf("zero second pass = %#v", plan.ZeroSecondPass)
	}
}

func TestPlanNativePhaseUnitScansRequiresScoreProvenance(t *testing.T) {
	raw := make([]byte, 0x50)
	raw[6] = 0
	if _, err := PlanNativePhaseUnitScans(raw, 1, nil); err == nil {
		t.Fatal("expected missing preselection scores to fail closed")
	}
}

func TestPlanNativePhaseUnitScansDoesNotRequireUnusedZeroScores(t *testing.T) {
	raw := make([]byte, 0x50)
	raw[6] = 1
	plan, err := PlanNativePhaseUnitScans(raw, 1, nil)
	if err != nil || len(plan.SelectorOne) != 1 ||
		len(plan.ZeroPreselection) != 0 || len(plan.ZeroSecondPass) != 0 {
		t.Fatalf("selector-one-only plan = %#v, %v", plan, err)
	}
}
