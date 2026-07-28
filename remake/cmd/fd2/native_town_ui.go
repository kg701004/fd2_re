package main

import (
	"errors"
	"path/filepath"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

type nativeTownUIAssets struct {
	scene *campaign.NativeTownAssets
}

// nativeTownMoveSelection preserves 0x2cf01..0x2cf65: right decrements and
// wraps normal 0 to 4; left increments and wraps every value above 4 to 0.
// This also defines how the revealed hidden selection 5 returns to the five
// normal facilities.
func nativeTownMoveSelection(selection, delta int) (int, bool) {
	if selection < 0 || selection > 5 || (delta != -1 && delta != 1) {
		return 0, false
	}
	selection += delta
	if selection < 0 {
		selection = 4
	}
	if selection > 4 {
		selection = 0
	}
	return selection, true
}

func loadNativeTownUIAssets() (*nativeTownUIAssets, error) {
	fdotherPath := nativeFDOTHERPath()
	if fdotherPath == "" {
		return nil, errors.New("native town UI: FDOTHER.DAT unavailable")
	}
	scene, err := campaign.DecodeNativeTownAssets(
		fdotherPath, filepath.Join(filepath.Dir(fdotherPath), "FDICON.B24"),
	)
	if err != nil {
		return nil, err
	}
	return &nativeTownUIAssets{scene: scene}, nil
}

func (g *Game) resetNativeTownUIPulse() {
	g.nativeTownUIClock.Reset()
	g.nativeTownUIPulse = 0
	g.nativeTownUILastTick = 0
	g.nativeTownUIHasTick = false
}

// 0x2d1b5 advances the four-state counter after a signed BIOS low-word delta
// of four. Counter 3 is rendered with FDICON sprite 1 by the compositor.
func (g *Game) stepNativeTownUIPulseTick(rawTick int) {
	if !g.nativeTownUIHasTick {
		g.nativeTownUILastTick = rawTick
		g.nativeTownUIHasTick = true
		return
	}
	delta := int16(uint16(rawTick) - uint16(g.nativeTownUILastTick))
	if delta < 4 {
		return
	}
	g.nativeTownUILastTick = rawTick
	g.nativeTownUIPulse = (g.nativeTownUIPulse + 1) & 3
}

func (g *Game) stepNativeTownUILifecycle(nowTick int) {
	if g.camp == nil || g.nativeTownUI == nil {
		return
	}
	n := g.camp.Node()
	if n == nil || n.Type != "town" || n.NativeTownVariant == nil {
		return
	}
	g.stepNativeTownUIPulseTick(nowTick)
}

func (g *Game) composeNativeTownFrame() ([]byte, bool) {
	if g.camp == nil || g.nativeTownUI == nil ||
		g.nativeTownUI.scene == nil || g.nativeClassUI == nil {
		return nil, false
	}
	n := g.camp.Node()
	if n == nil || n.Type != "town" || n.NativeTownVariant == nil {
		return nil, false
	}
	frame, err := campaign.ComposeNativeTownFrame(
		g.nativeTownUI.scene,
		g.nativeClassUI.strings,
		g.nativeClassUI.font,
		*n.NativeTownVariant,
		g.campSel,
		g.nativeTownUIPulse,
	)
	if err != nil {
		return nil, false
	}
	return frame, true
}

func (g *Game) drawNativeTown(screen *ebiten.Image) bool {
	frame, ok := g.composeNativeTownFrame()
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
	return true
}
