package battle

import "testing"

func TestNativeItemTargetPlanFromRowPreserves1BBDCCallFields(t *testing.T) {
	row := make([]byte, NativeItemEffectRowSize)
	row[0x0d], row[0x10], row[0x12], row[0x15] = 0x17, 3, 1, 2
	plan, err := NativeItemTargetPlanFromRow(row)
	if err != nil {
		t.Fatal(err)
	}
	if plan.ItemType != 0x17 || plan.SelectionMode != 3 || plan.SelectionInnerMark != 1 || plan.EffectMode != 1 || plan.TargetCode != 2 {
		t.Fatalf("plan=%+v", plan)
	}
	row[0x0d] = 5
	plan, err = NativeItemTargetPlanFromRow(row)
	if err != nil || plan.SelectionInnerMark != 0 {
		t.Fatalf("non-0x17 plan=%+v err=%v", plan, err)
	}
	if _, err := NativeItemTargetPlanFromRow(row[:len(row)-1]); err == nil {
		t.Fatal("short native item row unexpectedly accepted")
	}
}

func TestNativeItemEffectTargetsUsesConfirmedSecondStageOrigin(t *testing.T) {
	actor := &Unit{Camp: Own, X: 0, Y: 0, HP: 10, MaxHP: 10, OnField: true, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	confirmed := &Unit{Camp: Enemy, X: 2, Y: 0, HP: 10, MaxHP: 10, OnField: true}
	second := &Unit{Camp: Enemy, X: 3, Y: 0, HP: 10, MaxHP: 10, OnField: true}
	units := []*Unit{actor, confirmed, second}
	plan := NativeItemTargetPlan{SelectionMode: 2, EffectMode: 1, TargetCode: 0}
	targets, err := NativeItemEffectTargets(5, 1, actor, confirmed, plan, make([]byte, 5), units)
	if err != nil || len(targets) != 2 || targets[0] != confirmed || targets[1] != second {
		t.Fatalf("targets=%v err=%v", targets, err)
	}
}

func TestNativeItemEffectTargetsRejectsUnconfirmedCandidate(t *testing.T) {
	actor := &Unit{Camp: Own, X: 0, Y: 0, HP: 10, MaxHP: 10, OnField: true, HasNativeRecordByte6: true, NativeRecordByte6: 2}
	tooFar := &Unit{Camp: Enemy, X: 3, Y: 0, HP: 10, MaxHP: 10, OnField: true}
	plan := NativeItemTargetPlan{SelectionMode: 1, EffectMode: 1, TargetCode: 0}
	if _, err := NativeItemEffectTargets(4, 1, actor, tooFar, plan, make([]byte, 4), []*Unit{actor, tooFar}); err == nil {
		t.Fatal("non-candidate confirmation unexpectedly accepted")
	}
}
