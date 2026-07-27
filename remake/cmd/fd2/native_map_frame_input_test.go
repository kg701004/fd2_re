package main

import (
	"image/color"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/indexedmap"
)

func completeNativeMapFrameFixture(t *testing.T) (*nativeMapAssets, *MapData, *battle.State) {
	t.Helper()
	controls := []byte{0, 0, 0, 0}
	luts := make([][]byte, 10)
	for i := range luts {
		luts[i] = make([]byte, 256)
	}
	assets := &nativeMapAssets{
		Terrain: &fdicon.Bank{}, Range: &fdicon.Bank{}, Units: &fdicon.Bank{},
		Controls: controls, LUTs: luts, Palette: make(color.Palette, 256),
	}
	field := &MapData{
		W: 1, H: 1, Tiles: []int{0},
		NativeTileBlitModes:  []byte{0xff},
		NativeTerrainControl: append([]byte(nil), controls...),
	}
	unit := &battle.Unit{
		X: 0, Y: 0, MapSelectorKey: 7, HasMapSelectorKey: true,
		NativeRecordByte5: 0, HasNativeRecordByte5: true,
		BattleFig: 9, HasBattleFig: true,
		NativeRecordRace: 3, HasNativeRecordRace: true,
		NativeRecordClass: 4, HasNativeRecordClass: true,
	}
	state := &battle.State{}
	if err := state.AppendNativeMapSelectorBatch([]*battle.Unit{unit}); err != nil {
		t.Fatal(err)
	}
	return assets, field, state
}

func TestBuildNativeMapFrameInputUsesOnlyRawMaterializedState(t *testing.T) {
	assets, field, state := completeNativeMapFrameFixture(t)
	if !state.AdvanceNativeTerrainPhase(3, -1) {
		t.Fatal("terrain phase advance rejected")
	}
	state.NativeMapCycleState = fdicon.NativeMapSpriteCycleState{Idle: 2, Moving: 3}
	if !state.AdvanceNativeTerrainFlip(1) || !state.AdvanceNativeUnitPixelShift(1) {
		t.Fatal("binary map timing advance rejected")
	}
	runtime := nativeMapFrameRuntime{
		CameraX: 0, CameraY: 0,
		RangeMode: 0, CursorX: 0, CursorY: 0,
		HUD: indexedmap.NativeMapHUDInput{DisplayGateA: true, DisplayGateB: true, AnchorX: 1},
	}
	got, err := buildNativeMapFrameInput(assets, field, state, runtime)
	if err != nil {
		t.Fatal(err)
	}
	if got.Frame.TerrainCycle != 2 || got.Frame.IdleCycle != 2 || got.Frame.MovingCycle != 3 ||
		got.Frame.Flip != 1 || got.Frame.PixelShift != 1 ||
		got.Frame.RangeMode != 0 || got.Frame.ForegroundBank != assets.Terrain ||
		got.Frame.SelectorCache != state.NativeMapSelectorCache ||
		len(got.Frame.Units) != 1 || len(got.Frame.ForegroundUnits) != 1 ||
		got.HUDCache != state.NativeMapSelectorCache {
		t.Fatalf("frame input=%+v", got.Frame)
	}
}

func TestBuildNativeMapFrameInputRejectsControlDriftAndMissingRawRoster(t *testing.T) {
	assets, field, state := completeNativeMapFrameFixture(t)
	field.NativeTerrainControl[0] = 1
	if _, err := buildNativeMapFrameInput(assets, field, state, nativeMapFrameRuntime{}); err == nil {
		t.Fatal("accepted editable/native control-table drift")
	}
	field.NativeTerrainControl[0] = 0
	state.Units[0].HasBattleFig = false
	if got, err := buildNativeMapFrameInput(assets, field, state, nativeMapFrameRuntime{}); err == nil ||
		got.Frame.Units != nil || got.Frame.ForegroundUnits != nil {
		t.Fatalf("partial frame=%+v err=%v", got.Frame, err)
	}
}
