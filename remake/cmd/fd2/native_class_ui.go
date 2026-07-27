package main

import (
	"errors"
	"image"
	"image/color"
	"path/filepath"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

type nativeClassUIAssets struct {
	background []byte
	panel      fdother.LMI1Entry
	choices    []fdother.RawCell
	units      *fdicon.Bank
	strings    *fdtxt.Strings
	font       *fdtxt.Font
	palette    color.Palette
}

func loadNativeClassUIAssets() (*nativeClassUIAssets, error) {
	fdotherPath := nativeFDOTHERPath()
	if fdotherPath == "" {
		return nil, errors.New("native class UI: FDOTHER.DAT unavailable")
	}
	base := filepath.Dir(fdotherPath)
	resource14, err := fdother.ReadResource(fdotherPath, 14)
	if err != nil {
		return nil, err
	}
	entries, err := fdother.ParseLMI1(resource14)
	if err != nil || len(entries) <= 16 {
		if err != nil {
			return nil, err
		}
		return nil, errors.New("native class UI: FDOTHER#14 lacks entry 16")
	}
	backgroundFrame, err := fdother.ParseLMI1FrameEntry(resource14, 0)
	if err != nil || backgroundFrame.Width != 320 || backgroundFrame.Height != 200 {
		if err != nil {
			return nil, err
		}
		return nil, errors.New("native class UI: FDOTHER#14 entry 0 is not 320x200")
	}
	background := make([]byte, 320*200)
	if err := backgroundFrame.BlitAt(background, 320, 0, -1); err != nil {
		return nil, err
	}
	textRaw, err := fdother.ReadResource(filepath.Join(base, "FDTXT.DAT"), 0)
	if err != nil {
		return nil, err
	}
	strings, err := fdtxt.Parse(textRaw)
	if err != nil {
		return nil, err
	}
	fontRaw, err := fdother.ReadResource(fdotherPath, 4)
	if err != nil {
		return nil, err
	}
	font, err := fdtxt.ParseFont(fontRaw)
	if err != nil {
		return nil, err
	}
	units, err := fdicon.DecodeFile(filepath.Join(base, "FDICON.B24"))
	if err != nil {
		return nil, err
	}
	choices, err := fdother.DecodeRawCellResource(fdotherPath, 2)
	if err != nil {
		return nil, err
	}
	paletteRaw, err := fdother.ReadResource(fdotherPath, 0)
	if err != nil {
		return nil, err
	}
	palette, err := fdother.ParseVGAPalette(paletteRaw)
	if err != nil {
		return nil, err
	}
	palette[0] = color.NRGBA{A: 0xff}
	return &nativeClassUIAssets{
		background: background, panel: entries[16], units: units,
		choices: choices, strings: strings, font: font, palette: palette,
	}, nil
}

func (g *Game) composeNativeClassListFrame() ([]byte, bool) {
	a := g.nativeClassUI
	if a == nil || g.churchMode != "class" || len(g.churchIDs) == 0 {
		return nil, false
	}
	start, visible := campaign.NativeClassCandidateWindow(len(g.churchIDs), g.churchSel)
	if visible == 0 {
		return nil, false
	}
	rows := make([]campaign.NativeClassListRow, 0, visible)
	for row := 0; row < visible; row++ {
		id := g.churchIDs[start+row]
		unit, ok := g.partyRoster[id]
		if !ok || !unit.HasNativeIdentity || !unit.HasMapSelectorKey {
			return nil, false
		}
		target, ok := campaign.NativeClassChangeTarget(&unit, g.classChangeTable)
		if !ok {
			return nil, false
		}
		sprite, err := a.units.SpriteFor(unit.MapSelectorKey, 0, 0)
		if err != nil {
			return nil, false
		}
		rows = append(rows, campaign.NativeClassListRow{
			Sprite: sprite, NameTextIndex: unit.NativeIdentity + 1,
			CurrentClassTextID: unit.ClassID, TargetClassTextID: target.ClassID,
		})
	}
	frame, err := campaign.ComposeNativeClassListFrame(
		a.background, a.panel, rows, g.churchSel-start, a.strings, a.font,
	)
	if err != nil {
		return nil, false
	}
	return frame, true
}

func (g *Game) drawNativeClassList(screen *ebiten.Image) bool {
	frame, ok := g.composeNativeClassListFrame()
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
	return true
}

func (g *Game) nativeClassConfirmationState() (*nativeClassUIAssets, int, bool) {
	a := g.nativeClassUI
	if a == nil || g.churchMode != "class_confirm" || g.churchClassID < 0 {
		return nil, 0, false
	}
	unit, ok := g.partyRoster[g.churchClassID]
	if !ok || unit.Portrait < 0 {
		return nil, 0, false
	}
	return a, unit.Portrait + 1, true
}

func (g *Game) composeNativeClassConfirmationQuestion() ([]byte, bool) {
	a, nameTextIndex, ok := g.nativeClassConfirmationState()
	if !ok {
		return nil, false
	}
	frame, err := campaign.ComposeNativeClassConfirmationQuestion(
		a.background, a.strings, a.font, nameTextIndex,
	)
	return frame, err == nil
}

func (g *Game) composeNativeClassConfirmationFrame() ([]byte, bool) {
	a, nameTextIndex, ok := g.nativeClassConfirmationState()
	if !ok {
		return nil, false
	}
	frame, err := campaign.ComposeNativeClassConfirmationFrame(
		a.background, a.choices, a.strings, a.font,
		nameTextIndex, g.churchSel, g.nativeClassUIPulse/2,
	)
	if err != nil {
		return nil, false
	}
	return frame, true
}

func (g *Game) drawNativeClassConfirmation(screen *ebiten.Image) bool {
	frame, ok := g.composeNativeClassConfirmationFrame()
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
	return true
}

func (g *Game) presentNativeClassFrame(screen *ebiten.Image, frame []byte) {
	a := g.nativeClassUI
	paletted := image.NewPaletted(image.Rect(0, 0, 320, 200), a.palette)
	copy(paletted.Pix, frame)
	native := ebiten.NewImageFromImage(paletted)
	op := &ebiten.DrawImageOptions{}
	op.GeoM.Scale(2, 2)
	screen.DrawImage(native, op)
}
