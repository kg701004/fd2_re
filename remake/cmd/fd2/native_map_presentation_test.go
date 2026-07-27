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
