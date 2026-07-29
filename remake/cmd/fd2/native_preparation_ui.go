package main

import (
	"errors"
	"path/filepath"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

type nativePreparationUIAssets struct {
	roster *fdother.NativePreparationAssets
	status battle.NativeItemPanelDataAssets
}

func loadNativePreparationUIAssets() (*nativePreparationUIAssets, error) {
	fdotherPath := nativeFDOTHERPath()
	if fdotherPath == "" {
		return nil, errors.New("native preparation UI: FDOTHER.DAT unavailable")
	}
	roster, err := fdother.DecodeNativePreparationAssets(
		fdotherPath,
		filepath.Join(filepath.Dir(fdotherPath), "FDICON.B24"),
	)
	if err != nil {
		return nil, err
	}
	status, err := battle.LoadNativeItemPanelDataAssets(
		fdotherPath, filepath.Join(filepath.Dir(fdotherPath), "FDTXT.DAT"),
	)
	if err != nil {
		return nil, err
	}
	return &nativePreparationUIAssets{roster: roster, status: status}, nil
}

func (g *Game) composeNativePreparationFrame() ([]byte, bool) {
	if g.camp == nil || g.nativePreparationUI == nil || g.nativeClassUI == nil ||
		!g.prepSelecting || len(g.prepIDs) == 0 {
		return nil, false
	}
	n := g.camp.Node()
	if n == nil || n.Type != "preparation" {
		return nil, false
	}
	keys := make([]int, len(g.prepIDs))
	selected := make([]bool, len(g.prepIDs))
	for i, id := range g.prepIDs {
		unit, ok := g.partyRoster[id]
		if !ok || !unit.HasMapSelectorKey {
			return nil, false
		}
		keys[i] = unit.MapSelectorKey
		selected[i] = g.partyDeploy[id]
	}
	// 0x31e80 normalizes idle state 3 to frame 1. A dedicated BIOS-tick
	// lifecycle is still open, so production deliberately presents the
	// verified base state 0 rather than borrowing another screen's timer.
	frame, err := fdother.ComposeNativePreparationFrame(
		g.nativePreparationUI.roster,
		keys, selected, g.prepSel, 0, g.prepLimit,
	)
	if err != nil {
		return nil, false
	}
	unit := g.partyRoster[g.prepIDs[g.prepSel]]
	record, err := battle.NativeItemPanelRecordForUnit(&unit)
	if err != nil {
		return nil, false
	}
	if err := battle.RenderNativeItemPanelData(
		g.nativePreparationUI.status, record, frame,
	); err != nil {
		return nil, false
	}
	return frame, true
}

func (g *Game) drawNativePreparation(screen *ebiten.Image) bool {
	frame, ok := g.composeNativePreparationFrame()
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
	return true
}
