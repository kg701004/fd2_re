package fdother

import (
	"fmt"
	"reflect"
	"strings"
	"testing"
)

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

func completeNativePhaseCallbacks(calls *[]string) NativePhaseScanCallbacks {
	return NativePhaseScanCallbacks{
		Preselect: func(unit int) (NativePhasePreselectionScores, error) {
			*calls = append(*calls, fmt.Sprintf("preselect:%d", unit))
			return NativePhasePreselectionScores{}, nil
		},
		RunUnitAction: func(unit int, selector byte) (int, error) {
			*calls = append(
				*calls, fmt.Sprintf("action:%d:%d", unit, selector),
			)
			return nativeNoGlobalEventID, nil
		},
		RunGlobalEvent: func(eventID, unit int) error {
			*calls = append(
				*calls, fmt.Sprintf("global:%d:%d", eventID, unit),
			)
			return nil
		},
		ChapterIndex: func() (int, error) {
			*calls = append(*calls, "chapter-index")
			return 3, nil
		},
		RunChapterEvent: func(chapter, unit int) error {
			*calls = append(
				*calls, fmt.Sprintf("chapter:%d:%d", chapter, unit),
			)
			return nil
		},
		PendingCode: func() (int, error) {
			*calls = append(*calls, "pending")
			return 0, nil
		},
	}
}

func TestExecuteNativePhaseUnitScansRunsTailForEveryRecord(t *testing.T) {
	raw := make([]byte, 2*0x50)
	raw[6] = 1
	raw[0x50+6] = 2 // ineligible in all three passes
	var calls []string
	callbacks := completeNativePhaseCallbacks(&calls)
	callbacks.RunUnitAction = func(unit int, selector byte) (int, error) {
		calls = append(calls, fmt.Sprintf("action:%d:%d", unit, selector))
		return 7, nil
	}

	result, err := ExecuteNativePhaseUnitScans(raw, 2, callbacks)
	if err != nil {
		t.Fatal(err)
	}
	if result.Stopped {
		t.Fatalf("result = %#v", result)
	}
	want := []string{
		"action:0:1", "global:7:0", "chapter-index", "chapter:3:0", "pending",
		"chapter-index", "chapter:3:1", "pending",
		"chapter-index", "chapter:3:0", "pending",
		"chapter-index", "chapter:3:1", "pending",
		"chapter-index", "chapter:3:0", "pending",
		"chapter-index", "chapter:3:1", "pending",
	}
	if !reflect.DeepEqual(calls, want) {
		t.Fatalf("calls = %#v, want %#v", calls, want)
	}
}

func TestExecuteNativePhaseUnitScansRereadsBitSevenBeforeSecondPass(t *testing.T) {
	raw := make([]byte, 0x50)
	raw[6] = 0
	var calls []string
	callbacks := completeNativePhaseCallbacks(&calls)
	callbacks.Preselect = func(unit int) (NativePhasePreselectionScores, error) {
		calls = append(calls, fmt.Sprintf("preselect:%d", unit))
		return NativePhasePreselectionScores{
			SpellCandidateScore53C23: 6,
		}, nil
	}
	callbacks.RunUnitAction = func(unit int, selector byte) (int, error) {
		calls = append(calls, fmt.Sprintf("action:%d:%d", unit, selector))
		raw[unit*0x50+5] |= 0x80
		return nativeNoGlobalEventID, nil
	}

	if _, err := ExecuteNativePhaseUnitScans(raw, 1, callbacks); err != nil {
		t.Fatal(err)
	}
	var actions []string
	for _, call := range calls {
		if strings.HasPrefix(call, "action:") {
			actions = append(actions, call)
		}
	}
	if want := []string{"action:0:0"}; !reflect.DeepEqual(actions, want) {
		t.Fatalf("actions = %#v, want %#v", actions, want)
	}
}

func TestExecuteNativePhaseUnitScansLetsLowScoreReachSecondPass(t *testing.T) {
	raw := make([]byte, 0x50)
	raw[6] = 0
	var calls []string
	callbacks := completeNativePhaseCallbacks(&calls)
	callbacks.Preselect = func(unit int) (NativePhasePreselectionScores, error) {
		calls = append(calls, fmt.Sprintf("preselect:%d", unit))
		return NativePhasePreselectionScores{
			SpellCandidateScore53C23: 5,
			ItemCommandScore53C33:    5,
		}, nil
	}

	if _, err := ExecuteNativePhaseUnitScans(raw, 1, callbacks); err != nil {
		t.Fatal(err)
	}
	var actions []string
	for _, call := range calls {
		if strings.HasPrefix(call, "action:") {
			actions = append(actions, call)
		}
	}
	if want := []string{"action:0:0"}; !reflect.DeepEqual(actions, want) {
		t.Fatalf("actions = %#v, want %#v", actions, want)
	}
}

func TestExecuteNativePhaseUnitScansChecksPendingAfterChapterEvent(t *testing.T) {
	raw := make([]byte, 2*0x50)
	raw[6] = 1
	raw[0x50+6] = 1
	var calls []string
	pending := 0
	callbacks := completeNativePhaseCallbacks(&calls)
	callbacks.RunGlobalEvent = func(eventID, unit int) error {
		calls = append(calls, fmt.Sprintf("global:%d:%d", eventID, unit))
		pending = 1
		return nil
	}
	callbacks.RunUnitAction = func(unit int, selector byte) (int, error) {
		calls = append(calls, fmt.Sprintf("action:%d:%d", unit, selector))
		return 9, nil
	}
	callbacks.PendingCode = func() (int, error) {
		calls = append(calls, "pending")
		return pending, nil
	}

	result, err := ExecuteNativePhaseUnitScans(raw, 2, callbacks)
	if err != nil {
		t.Fatal(err)
	}
	if !result.Stopped || result.Pass != NativePhaseScanSelectorOne ||
		result.UnitIndex != 0 || result.PendingCode != 1 {
		t.Fatalf("result = %#v", result)
	}
	want := []string{
		"action:0:1", "global:9:0", "chapter-index", "chapter:3:0", "pending",
	}
	if !reflect.DeepEqual(calls, want) {
		t.Fatalf("calls = %#v, want %#v", calls, want)
	}
}

func TestExecuteNativePhaseUnitScansFailsClosedOnTableBounds(t *testing.T) {
	raw := make([]byte, 0x50)
	raw[6] = 1
	var calls []string
	callbacks := completeNativePhaseCallbacks(&calls)
	callbacks.RunUnitAction = func(int, byte) (int, error) {
		return nativeGlobalEventCount, nil
	}
	if _, err := ExecuteNativePhaseUnitScans(raw, 1, callbacks); err == nil {
		t.Fatal("expected out-of-range global event index to fail closed")
	}

	callbacks = completeNativePhaseCallbacks(&calls)
	callbacks.ChapterIndex = func() (int, error) {
		return nativeChapterEventCount, nil
	}
	if _, err := ExecuteNativePhaseUnitScans(raw, 1, callbacks); err == nil {
		t.Fatal("expected out-of-range chapter index to fail closed")
	}
}

func TestExecuteNativePhaseUnitScansRequiresEveryNativeTailCallback(t *testing.T) {
	raw := make([]byte, 0x50)
	callbacks := completeNativePhaseCallbacks(new([]string))
	callbacks.RunChapterEvent = nil
	if _, err := ExecuteNativePhaseUnitScans(raw, 1, callbacks); err == nil {
		t.Fatal("expected missing chapter callback to fail closed")
	}
}
