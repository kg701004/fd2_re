package battle

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
)

func TestNativeMapPresentationPreservesSevenTickGridLifecycle(t *testing.T) {
	u := &Unit{X: 4, Y: 5, Dir: 3, OffX: 7, OffY: 8}
	if err := u.MaterializeNativeMapPresentation(); err != nil {
		t.Fatal(err)
	}
	if u.NativeMapPresentation != (NativeMapPresentationState{X: 4, Y: 5}) ||
		u.Dir != 0 || u.OffX != 0 || u.OffY != 0 {
		t.Fatalf("constructor state=%+v normalized=(%d,%v,%v)",
			u.NativeMapPresentation, u.Dir, u.OffX, u.OffY)
	}
	for motion := 1; motion <= 6; motion++ {
		if !u.SetNativeMapGridMotion(3, motion) {
			t.Fatalf("motion %d rejected", motion)
		}
		if u.NativeMapPresentation.X != 4 || u.NativeMapPresentation.Y != 5 ||
			u.NativeMapPresentation.Motion != byte(motion) {
			t.Fatalf("motion %d state=%+v", motion, u.NativeMapPresentation)
		}
	}
	if !u.FinishNativeMapGridStep(3, 5, 5) {
		t.Fatal("seventh-tick commit rejected")
	}
	if u.NativeMapPresentation != (NativeMapPresentationState{X: 5, Y: 5, Pose: 3}) ||
		u.X != 5 || u.Y != 5 || u.Dir != 3 {
		t.Fatalf("completed state=%+v normalized=(%d,%d,%d)",
			u.NativeMapPresentation, u.X, u.Y, u.Dir)
	}
}

func TestNativeUnitLayerEntryRequiresCompleteRawProvenance(t *testing.T) {
	u := &Unit{
		X: 2, Y: 3, MapSelectorSlot: 4, HasMapSelectorSlot: true,
		NativeRecordByte5: 0x81, HasNativeRecordByte5: true,
		NativeTransient: [6]byte{0, 0, 0, 0, 2},
	}
	if _, ok := u.NativeUnitLayerEntry(); ok {
		t.Fatal("accepted unit without materialized raw presentation")
	}
	if err := u.MaterializeNativeMapPresentation(); err != nil {
		t.Fatal(err)
	}
	if !u.SetNativeMapGridMotion(2, 6) {
		t.Fatal("raw motion rejected")
	}
	entry, ok := u.NativeUnitLayerEntry()
	if !ok || entry != (fdicon.NativeUnitLayerEntry{
		X: 2, Y: 3, Slot: 4, Pose: 2, MotionOffset: 6,
		Flags: 0x81, ForceBase: true, Inactive: true,
	}) {
		t.Fatalf("entry=%+v ok=%v", entry, ok)
	}
}

func TestMaterializeNativeMapSelectorSlotsIsAtomicOnInvalidCoordinate(t *testing.T) {
	cache := &fdicon.NativeSelectorCache{}
	units := []*Unit{
		{X: 1, Y: 2, MapSelectorKey: 7, HasMapSelectorKey: true},
		{X: 0x100, Y: 2, MapSelectorKey: 8, HasMapSelectorKey: true},
	}
	if err := MaterializeNativeMapSelectorSlots(units, cache); err == nil {
		t.Fatal("accepted native coordinate outside byte range")
	}
	for i, u := range units {
		if u.HasMapSelectorSlot || u.HasNativeMapPresentation {
			t.Fatalf("unit %d partially materialized: %+v", i, u)
		}
	}
}

func TestStateOwnsNativeMapCycleGlobalsAfterConstruction(t *testing.T) {
	st := &State{}
	if st.AdvanceNativeMapPresentationCycles(5) {
		t.Fatal("legacy state accepted native cycle update")
	}
	if err := st.AppendNativeMapSelectorBatch([]*Unit{{
		X: 1, Y: 2, MapSelectorKey: 7, HasMapSelectorKey: true,
	}}); err != nil {
		t.Fatal(err)
	}
	if !st.HasNativeMapCycleState || !st.AdvanceNativeMapPresentationCycles(5) {
		t.Fatal("native cycle globals were not materialized")
	}
	if st.NativeMapCycleState != (fdicon.NativeMapSpriteCycleState{
		Idle: 1, Moving: 1, LastTimerTick: 5,
	}) {
		t.Fatalf("first cycle call=%+v", st.NativeMapCycleState)
	}
	if !st.AdvanceNativeMapPresentationCycles(6) ||
		st.NativeMapCycleState != (fdicon.NativeMapSpriteCycleState{
			Idle: 1, Moving: 2, LastTimerTick: 5,
		}) {
		t.Fatalf("gated cycle call=%+v", st.NativeMapCycleState)
	}
}
