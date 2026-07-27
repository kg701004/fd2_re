package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestBattleWalkPreservesNativeSevenTickRecordLifecycle(t *testing.T) {
	u := &battle.Unit{X: 2, Y: 3}
	if err := u.MaterializeNativeMapPresentation(); err != nil {
		t.Fatal(err)
	}
	g := &Game{
		m: &MapData{TileW: 24, TileH: 24},
		walk: &walkAnim{
			u:    u,
			path: []battle.Cell{{X: 2, Y: 3}, {X: 3, Y: 3}},
		},
	}
	for tick := 1; tick <= 6; tick++ {
		g.stepBattleWalk()
		raw := u.NativeMapPresentation
		if raw.X != 2 || raw.Y != 3 || raw.Pose != 3 || raw.Motion != byte(tick) {
			t.Fatalf("tick %d raw=%+v", tick, raw)
		}
		if u.X != 2 || u.Y != 3 || u.OffX <= 0 {
			t.Fatalf("tick %d normalized=(%d,%d off=%v)", tick, u.X, u.Y, u.OffX)
		}
	}
	g.stepBattleWalk()
	if g.walk != nil || !g.moved || !g.ring {
		t.Fatalf("seventh tick did not finish player walk: walk=%v moved=%v ring=%v", g.walk, g.moved, g.ring)
	}
	if u.NativeMapPresentation != (battle.NativeMapPresentationState{X: 3, Y: 3, Pose: 3}) ||
		u.X != 3 || u.Y != 3 || u.OffX != 0 || u.OffY != 0 {
		t.Fatalf("seventh tick raw=%+v normalized=(%d,%d,%v,%v)",
			u.NativeMapPresentation, u.X, u.Y, u.OffX, u.OffY)
	}
}

func TestOriginalActingUpdatesMaterializedRawPresentation(t *testing.T) {
	slot := 0
	u := &battle.Unit{X: 4, Y: 5}
	if err := u.MaterializeNativeMapPresentation(); err != nil {
		t.Fatal(err)
	}
	g := &Game{
		m:  &MapData{TileW: 24, TileH: 24},
		st: &battle.State{Units: []*battle.Unit{u}},
	}
	j := &actPoseJob{acting: []campaign.ActingFrame{{
		Beats: 1,
		Units: []campaign.ActingUnit{{Slot: &slot, Pose: 2}},
	}}}
	g.beginActingFrame(j)
	for tick := 1; tick <= 6; tick++ {
		g.stepOriginalActing(j)
		raw := u.NativeMapPresentation
		if raw.X != 4 || raw.Y != 5 || raw.Pose != 2 || raw.Motion != byte(tick) {
			t.Fatalf("acting tick %d raw=%+v", tick, raw)
		}
	}
	g.stepOriginalActing(j)
	if u.NativeMapPresentation != (battle.NativeMapPresentationState{X: 4, Y: 4, Pose: 2}) ||
		u.X != 4 || u.Y != 4 {
		t.Fatalf("acting completion raw=%+v normalized=(%d,%d)",
			u.NativeMapPresentation, u.X, u.Y)
	}
}

func TestGameCursorUsesMaterializedNativeMapView(t *testing.T) {
	st := &battle.State{W: 30, H: 30}
	if err := st.MaterializeNativeMapViewState(battle.NativeMapViewState{
		CameraX: 4, CameraY: 5, CursorX: 15, CursorY: 11,
		VisibleCursorX: 11, VisibleCursorY: 6,
	}); err != nil {
		t.Fatal(err)
	}
	if !st.MaterializeNativeMapHUDState(1, 1, 0xf2) {
		t.Fatal("HUD state rejected")
	}
	g := &Game{m: &MapData{W: 30, H: 30, TileW: 24, TileH: 24}, st: st}
	g.moveMapCursor(1, 0)
	if g.curX != 16 || g.curY != 11 || g.camX != 5*24 || g.camY != 5*24 {
		t.Fatalf("game view cursor=(%d,%d) camera=(%v,%v)",
			g.curX, g.curY, g.camX, g.camY)
	}
	if st.NativeMapHUDState.AnchorX != 1 {
		t.Fatalf("HUD anchor did not follow visible cursor: %+v", st.NativeMapHUDState)
	}
}

func TestScreenshotCursorUsesNativeViewAndHUDStateMachine(t *testing.T) {
	st := &battle.State{W: 30, H: 30}
	if err := st.MaterializeNativeMapViewState(battle.NativeMapViewState{
		CameraX: 1, CameraY: 13, CursorX: 8, CursorY: 17,
		VisibleCursorX: 7, VisibleCursorY: 4,
	}); err != nil {
		t.Fatal(err)
	}
	if !st.MaterializeNativeMapHUDState(1, 1, 1) {
		t.Fatal("HUD state rejected")
	}
	g := &Game{m: &MapData{W: 30, H: 30, TileW: 24, TileH: 24}, st: st}
	g.syncNativeMapView()
	if !g.positionScreenshotCursor(8, 15) {
		t.Fatal("screenshot cursor rejected")
	}
	view := st.NativeMapViewState
	if view.CameraX != 1 || view.CameraY != 13 ||
		view.CursorX != 8 || view.CursorY != 15 ||
		view.VisibleCursorX != 7 || view.VisibleCursorY != 2 ||
		g.curX != 8 || g.curY != 15 {
		t.Fatalf("screenshot view=%+v game=(%d,%d)", view, g.curX, g.curY)
	}
	if st.NativeMapHUDState.AnchorX != 1 {
		t.Fatalf("screenshot HUD anchor=%+v", st.NativeMapHUDState)
	}
}

func TestGameMaterializesEditableNativeMapRuntime(t *testing.T) {
	rangeMode := 1
	g := &Game{
		m:  &MapData{W: 24, H: 24, TileW: 24, TileH: 24},
		st: &battle.State{W: 24, H: 24},
	}
	n := &campaign.Node{
		NativeMapView: &campaign.NativeMapViewConfig{
			CameraX: 1, CameraY: 13, CursorX: 8, CursorY: 17,
			VisibleCursorX: 7, VisibleCursorY: 4,
			RangeMode: &rangeMode,
		},
		NativeMapHUD: &campaign.NativeMapHUDConfig{
			DisplayGateA: 1, DisplayGateB: 1, AnchorX: 1,
		},
	}
	if !g.materializeNativeMapRuntime(n) {
		t.Fatal(g.loadErr)
	}
	if !g.st.HasNativeMapViewState || !g.st.HasNativeMapHUDState ||
		!g.st.HasNativeMapRangeModeState || g.st.NativeMapRangeMode != 1 ||
		g.curX != 8 || g.curY != 17 || g.camX != 24 || g.camY != 13*24 {
		t.Fatalf("materialized game=%+v view=%+v HUD=%+v",
			g, g.st.NativeMapViewState, g.st.NativeMapHUDState)
	}
}

func TestGameRejectsInvalidEditableNativeMapRuntime(t *testing.T) {
	rangeMode := 1
	g := &Game{
		m:  &MapData{W: 24, H: 24, TileW: 24, TileH: 24},
		st: &battle.State{W: 24, H: 24},
	}
	n := &campaign.Node{
		NativeMapView: &campaign.NativeMapViewConfig{
			CameraX: 1, CameraY: 13, CursorX: 8, CursorY: 17,
			VisibleCursorX: 8, VisibleCursorY: 4,
			RangeMode: &rangeMode,
		},
		NativeMapHUD: &campaign.NativeMapHUDConfig{
			DisplayGateA: 1, DisplayGateB: 1, AnchorX: 1,
		},
	}
	if g.materializeNativeMapRuntime(n) || g.loadErr == "" ||
		g.st.HasNativeMapViewState || g.st.HasNativeMapHUDState {
		t.Fatalf("invalid native runtime was not rejected: err=%q state=%+v", g.loadErr, g.st)
	}
}

func TestGameRejectsUnmaterializedDynamicCampaignSelector(t *testing.T) {
	rangeMode := 11
	g := &Game{
		m:  &MapData{W: 24, H: 24, TileW: 24, TileH: 24},
		st: &battle.State{W: 24, H: 24},
	}
	n := &campaign.Node{
		NativeMapView: &campaign.NativeMapViewConfig{
			CameraX: 1, CameraY: 13, CursorX: 8, CursorY: 17,
			VisibleCursorX: 7, VisibleCursorY: 4,
			RangeMode: &rangeMode,
		},
		NativeMapHUD: &campaign.NativeMapHUDConfig{
			DisplayGateA: 1, DisplayGateB: 1, AnchorX: 1,
		},
	}
	if g.materializeNativeMapRuntime(n) || g.loadErr == "" ||
		g.st.HasNativeMapRangeModeState {
		t.Fatalf("runtime-owned selector was accepted as campaign bootstrap: err=%q state=%+v", g.loadErr, g.st)
	}
}
