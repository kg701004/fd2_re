package main

import (
	"errors"
	"path/filepath"
	"time"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

type nativePreparationUIAssets struct {
	roster   *fdother.NativePreparationAssets
	status   battle.NativeItemPanelDataAssets
	choices  []fdother.RawCell
	dialogue []fdother.RawCell
	portrait dato.Frame
}

func (g *Game) stepNativePreparationCycleTick(rawTick int) {
	state := fdicon.AdvanceNativeMapSpriteCycles(
		fdicon.NativeMapSpriteCycleState{
			Idle: g.prepIdleCycle, LastTimerTick: g.prepLastTick,
		},
		rawTick,
	)
	g.prepIdleCycle = state.Idle
	g.prepLastTick = state.LastTimerTick
}

func (g *Game) stepNativePreparationUILifecycle(now time.Time) {
	if g.camp == nil || g.nativePreparationUI == nil || !g.prepSelecting {
		return
	}
	n := g.camp.Node()
	if n == nil || n.Type != "preparation" {
		return
	}
	g.stepNativePreparationCycleTick(g.prepClock.Sample(now))
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
	choices, err := fdother.DecodeRawCellResource(fdotherPath, 2)
	if err != nil {
		return nil, err
	}
	resource5, err := fdother.ReadResource(fdotherPath, 5)
	if err != nil {
		return nil, err
	}
	dialogue := make([]fdother.RawCell, 20)
	for index := 1; index <= 19; index++ {
		dialogue[index], err = fdother.ParseLMI1RawEntry(resource5, index)
		if err != nil {
			return nil, err
		}
	}
	portraits, err := dato.DecodeResource(filepath.Join(filepath.Dir(fdotherPath), "DATO.DAT"), 0x4b)
	if err != nil || len(portraits) == 0 {
		if err != nil {
			return nil, err
		}
		return nil, errors.New("native preparation UI: DATO#75 has no frames")
	}
	return &nativePreparationUIAssets{
		roster: roster, status: status, choices: choices,
		dialogue: dialogue, portrait: portraits[0],
	}, nil
}

func (g *Game) composeNativePreparationFrame() ([]byte, bool) {
	if g.camp == nil || g.nativePreparationUI == nil || g.nativeClassUI == nil ||
		(!g.prepSelecting && !g.prepConfirm) || len(g.prepIDs) == 0 {
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
	cycle, err := fdicon.NativeFrameIndex(0, false, g.prepIdleCycle, 0)
	if err != nil {
		return nil, false
	}
	frame, err := fdother.ComposeNativePreparationFrame(
		g.nativePreparationUI.roster,
		keys, selected, g.prepSel, cycle, g.prepLimit,
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

func (g *Game) composeNativePreparationConfirmationFrame() ([]byte, bool) {
	if !g.prepConfirm || g.nativeClassUI == nil {
		return nil, false
	}
	background, ok := g.composeNativePreparationFrame()
	if !ok {
		return nil, false
	}
	frame, err := campaign.ComposeNativePreparationConfirmationFrame(
		background,
		g.nativePreparationUI.choices,
		g.nativePreparationUI.dialogue,
		g.nativePreparationUI.portrait,
		g.nativePreparationUI.status.Strings,
		g.nativePreparationUI.status.Font,
		g.prepConfirmSel,
		0,
	)
	if err != nil {
		return nil, false
	}
	return frame, true
}

func (g *Game) drawNativePreparation(screen *ebiten.Image) bool {
	var (
		frame []byte
		ok    bool
	)
	if g.prepConfirm {
		frame, ok = g.composeNativePreparationConfirmationFrame()
	} else {
		frame, ok = g.composeNativePreparationFrame()
	}
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
	return true
}
