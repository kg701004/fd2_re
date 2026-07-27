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
	if !st.HasNativeTerrainPhaseState || !st.AdvanceNativeTerrainPhase(3, -1) ||
		st.NativeTerrainPhaseState.Phase != 1 {
		t.Fatalf("terrain phase state=%+v valid=%v",
			st.NativeTerrainPhaseState, st.HasNativeTerrainPhaseState)
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

func TestNativeMapFrameRosterRequiresCompleteRawRoster(t *testing.T) {
	st := &State{}
	u := &Unit{
		X: 1, Y: 2, MapSelectorKey: 7, HasMapSelectorKey: true,
		NativeRecordByte5: 0x80, HasNativeRecordByte5: true,
		BattleFig: 9, HasBattleFig: true,
		NativeRecordRace: 3, HasNativeRecordRace: true,
		NativeRecordClass: 4, HasNativeRecordClass: true,
	}
	if err := st.AppendNativeMapSelectorBatch([]*Unit{u}); err != nil {
		t.Fatal(err)
	}
	if !u.SetNativeMapGridMotion(1, 5) {
		t.Fatal("raw motion rejected")
	}
	roster, err := st.NativeMapFrameRoster()
	if err != nil {
		t.Fatal(err)
	}
	if len(roster.Units) != 1 || len(roster.Foreground) != 1 ||
		roster.Units[0].MotionOffset != 5 ||
		roster.Foreground[0] != (fdicon.NativeForegroundLayerEntry{
			X: 1, Y: 2, Pose: 1, MotionOffset: 5,
			Unit7: 9, Race: 3, Class: 4,
		}) {
		t.Fatalf("roster=%+v", roster)
	}

	u.HasBattleFig = false
	if _, err := st.NativeMapFrameRoster(); err == nil {
		t.Fatal("accepted legacy BattleFig fallback as raw unit+7")
	}
}

func TestNativeMapFrameRosterDoesNotReturnPartialInput(t *testing.T) {
	st := &State{}
	units := []*Unit{
		{
			X: 1, Y: 2, MapSelectorKey: 7, HasMapSelectorKey: true,
			NativeRecordByte5: 0, HasNativeRecordByte5: true,
			BattleFig: 9, HasBattleFig: true,
			NativeRecordRace: 3, HasNativeRecordRace: true,
			NativeRecordClass: 4, HasNativeRecordClass: true,
		},
		{
			X: 3, Y: 4, MapSelectorKey: 8, HasMapSelectorKey: true,
			NativeRecordByte5: 0, HasNativeRecordByte5: true,
			BattleFig: 10, HasBattleFig: true,
			NativeRecordRace: 5, HasNativeRecordRace: true,
		},
	}
	if err := st.AppendNativeMapSelectorBatch(units); err != nil {
		t.Fatal(err)
	}
	roster, err := st.NativeMapFrameRoster()
	if err == nil || roster.Units != nil || roster.Foreground != nil {
		t.Fatalf("partial roster=%+v err=%v", roster, err)
	}
}
