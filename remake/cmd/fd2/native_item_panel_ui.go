package main

import (
	"image"
	"image/color"
	"os"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func nativeOriginalArchivePath(environment, name string) string {
	if path := os.Getenv(environment); path != "" {
		return path
	}
	path := assetPath("assets/original/" + name)
	if fileExists(path) {
		return path
	}
	return ""
}

func nativeFDTXTPath() string {
	return nativeOriginalArchivePath("FD2_ORIGINAL_FDTXT", "FDTXT.DAT")
}

func nativeDATOPath() string {
	return nativeOriginalArchivePath("FD2_ORIGINAL_DATO", "DATO.DAT")
}

func nativeItemRawSlots(unit *battle.Unit) []int {
	if unit == nil || len(unit.InventorySlots) != 8 || len(unit.NativeInventoryFlags) != 8 {
		return nil
	}
	slots := make([]int, 0, 8)
	for slot := 0; slot < 8; slot++ {
		if unit.NativeInventoryFlags[slot]&0x80 == 0 {
			slots = append(slots, slot)
		}
	}
	return slots
}

func (g *Game) prepareNativeItemPanel(unit *battle.Unit) bool {
	g.clearNativeItemPanel()
	fdotherPath, fdtxtPath, datoPath := nativeFDOTHERPath(), nativeFDTXTPath(), nativeDATOPath()
	if fdotherPath == "" || fdtxtPath == "" || datoPath == "" || len(g.nativeUIPalette) < 256 {
		return false
	}
	record, err := battle.NativeItemPanelRecordForUnit(unit)
	if err != nil {
		return false
	}
	pixels := make([]byte, 320*200)
	if err := battle.RenderNativeItemPanelResources(fdotherPath, fdtxtPath, datoPath, record, pixels); err != nil {
		return false
	}
	assets, err := battle.LoadNativeItemPanelDataAssets(fdotherPath, fdtxtPath)
	if err != nil {
		return false
	}
	rows, err := battle.LoadNativeItemEffectRowPrefix(assetPath("assets/data/native_item_effect_rows.json"))
	if err != nil {
		return false
	}
	g.nativeItemPanelBase = pixels
	g.nativeItemPanelRecord = record
	g.nativeItemPanelAssets = &assets
	g.nativeItemEffectRows = rows
	return g.refreshNativeItemPanel(unit)
}

func (g *Game) refreshNativeItemPanel(unit *battle.Unit) bool {
	if len(g.nativeItemPanelBase) != 320*200 || len(g.nativeItemPanelRecord) != 80 ||
		g.nativeItemPanelAssets == nil || len(g.nativeItemEffectRows) == 0 {
		return false
	}
	rawSlots := nativeItemRawSlots(unit)
	if len(rawSlots) == 0 {
		return false
	}
	if g.itemSel < 0 {
		g.itemSel = 0
	}
	if g.itemSel >= len(rawSlots) {
		g.itemSel = len(rawSlots) - 1
	}
	pixels := append([]byte(nil), g.nativeItemPanelBase...)
	if err := battle.RenderNativeItemPanelRows(
		*g.nativeItemPanelAssets, g.nativeItemPanelRecord,
		rawSlots[g.itemSel], g.nativeItemEffectRows, pixels,
	); err != nil {
		return false
	}
	palette := append(color.Palette(nil), g.nativeUIPalette...)
	palette[0] = color.NRGBA{A: 0xff}
	frame := image.NewPaletted(image.Rect(0, 0, 320, 200), palette)
	copy(frame.Pix, pixels)
	g.nativeItemPanel = ebiten.NewImageFromImage(frame)
	return true
}

func (g *Game) clearNativeItemPanel() {
	g.nativeItemPanel = nil
	g.nativeItemPanelBase = nil
	g.nativeItemPanelRecord = nil
	g.nativeItemPanelAssets = nil
	g.nativeItemEffectRows = nil
	g.itemAnimStep = 0
	g.itemClosing = false
}

// stepNativeItemPanelAnimation returns true while input must remain blocked.
func (g *Game) stepNativeItemPanelAnimation() bool {
	if g.nativeItemPanel == nil {
		return false
	}
	if g.itemClosing {
		if g.itemAnimStep < 11 {
			g.itemAnimStep++
			return true
		}
		g.itemOpen, g.ring = false, true
		g.clearNativeItemPanel()
		return true
	}
	if g.itemAnimStep < 11 {
		g.itemAnimStep++
		return true
	}
	return false
}

func (g *Game) beginNativeItemPanelClose() {
	if g.nativeItemPanel == nil {
		g.itemOpen, g.ring = false, true
		return
	}
	g.itemClosing = true
	g.itemAnimStep = 0
}

func (g *Game) drawNativeItemPanel(screen *ebiten.Image) bool {
	if g.nativeItemPanel == nil {
		return false
	}
	frame := 11 - g.itemAnimStep
	if g.itemClosing {
		frame = g.itemAnimStep
	}
	if frame < 0 {
		frame = 0
	}
	if frame > 11 {
		frame = 11
	}
	pass, err := battle.NativeItemPanelFrameFor(frame)
	if err != nil {
		return false
	}
	for _, region := range []battle.NativeItemPanelRegion{pass.Left, pass.Upper, pass.Bottom} {
		if !region.Enabled || region.Width <= 0 || region.Height <= 0 {
			continue
		}
		source := g.nativeItemPanel.SubImage(image.Rect(
			region.SourceX, region.SourceY,
			region.SourceX+region.Width, region.SourceY+region.Height,
		)).(*ebiten.Image)
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Scale(2, 2)
		op.GeoM.Translate(float64(region.DestX*2), float64(region.DestY*2))
		screen.DrawImage(source, op)
	}
	return true
}
