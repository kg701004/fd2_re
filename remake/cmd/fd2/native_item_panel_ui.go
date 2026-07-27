package main

import (
	"encoding/binary"
	"fmt"
	"image"
	"image/color"
	"os"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
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

// applyNativeImmediateItem executes only the fully closed, non-RNG type
// 8/9/10 transaction. Their tracked rows use selection/effect mode zero, so
// actor confirmation is still validated through the recovered two-stage
// target planner instead of being assumed from the item name.
func (g *Game) applyNativeImmediateItem(rawSlot, itemID int) (bool, error) {
	if g == nil || g.st == nil || g.sel == nil {
		return false, fmt.Errorf("native item transaction context is unavailable")
	}
	rowOffset, err := battle.NativeItemEffectRowOffset(itemID)
	if err != nil || rowOffset+battle.NativeItemEffectRowSize > len(g.nativeItemEffectRows) {
		return false, fmt.Errorf("native item row %d is unavailable", itemID)
	}
	row := g.nativeItemEffectRows[rowOffset : rowOffset+battle.NativeItemEffectRowSize]
	wordRoute, wordSupported := battle.NativeItemWordDeltaRouteForType(int(row[0x0d]))
	delta := binary.LittleEndian.Uint16(row[0x0e:0x10])
	capacityRoute, capacitySupported := battle.NativeItemCapacityStepRouteForType(row[0x0d], delta)
	if !wordSupported && !capacitySupported {
		return false, nil
	}
	plan, err := battle.NativeItemTargetPlanFromRow(row)
	if err != nil {
		return false, err
	}
	targets, err := battle.NativeItemEffectTargets(
		g.st.W, g.st.H, g.sel, g.sel, plan,
		g.st.NativeTargetFlags, g.st.Units,
	)
	if err != nil {
		return false, err
	}
	if len(targets) != 1 || targets[0] != g.sel {
		return false, fmt.Errorf("native immediate item target list is not actor-only")
	}
	if wordSupported {
		if g.shopItemStats == nil {
			return false, fmt.Errorf("native equipment recomputation table is unavailable")
		}
		for index, equipped := range g.sel.Equipped {
			if equipped && index < len(g.sel.Inventory) {
				if _, ok := g.shopItemStats[g.sel.Inventory[index]]; !ok {
					return false, fmt.Errorf("native equipped item %d is absent from recomputation table", g.sel.Inventory[index])
				}
			}
		}
		if _, err := battle.ApplyNativeItemBaseStatDeltaToUnit(
			g.sel, g.sel, wordRoute, delta, rawSlot,
		); err != nil {
			return false, err
		}
		campaign.RecomputeEquipment(g.sel, g.shopItemStats)
	} else {
		if _, err := battle.ApplyNativeItemCapacityToUnit(
			g.sel, g.sel, capacityRoute, rawSlot,
		); err != nil {
			return false, err
		}
	}
	// 0x1bbdc calls 0x13512 immediately after successful 0x20c6f.
	g.sel.NativeRecordByte5 |= 0x80
	g.sel.HasNativeRecordByte5 = true
	g.sel.Acted = true
	g.itemOpen, g.ring = false, false
	g.clearNativeItemPanel()
	g.sel, g.reach, g.moved = nil, nil, false
	return true, nil
}

// beginNativeRestoreItem enters the recovered first-stage 0x14818 selector
// only for the closed HP/MP restore families. The mutation remains deferred
// until a concrete runtime unit passes both target-planner stages.
func (g *Game) beginNativeRestoreItem(rawSlot, itemID int) (bool, error) {
	rowOffset, err := battle.NativeItemEffectRowOffset(itemID)
	if err != nil || rowOffset+battle.NativeItemEffectRowSize > len(g.nativeItemEffectRows) {
		return false, fmt.Errorf("native item row %d is unavailable", itemID)
	}
	row := g.nativeItemEffectRows[rowOffset : rowOffset+battle.NativeItemEffectRowSize]
	amount := binary.LittleEndian.Uint16(row[0x0e:0x10])
	if _, ok := battle.NativeItemHPRestoreRouteForType(row[0x0d], amount); !ok {
		if _, ok := battle.NativeItemMPRestoreRouteForType(row[0x0d], amount); !ok {
			return false, nil
		}
	}
	if _, err := battle.NativeItemTargetPlanFromRow(row); err != nil {
		return false, err
	}
	g.nativeItemTargeting = true
	g.nativeItemTargetID = itemID
	g.nativeItemTargetRawSlot = rawSlot
	g.itemOpen = false
	rows := g.nativeItemEffectRows
	g.clearNativeItemPanel()
	g.nativeItemEffectRows = rows
	g.curX, g.curY = g.sel.X, g.sel.Y
	g.reach = nil
	return true, nil
}

func (g *Game) nativeItemSelectionTargets() []*battle.Unit {
	if g == nil || g.st == nil || g.sel == nil || !g.nativeItemTargeting {
		return nil
	}
	rowOffset, err := battle.NativeItemEffectRowOffset(g.nativeItemTargetID)
	if err != nil || rowOffset+battle.NativeItemEffectRowSize > len(g.nativeItemEffectRows) {
		return nil
	}
	plan, err := battle.NativeItemTargetPlanFromRow(
		g.nativeItemEffectRows[rowOffset : rowOffset+battle.NativeItemEffectRowSize],
	)
	if err != nil {
		return nil
	}
	targets, err := battle.NativeAttackCandidates(
		g.st.W, g.st.H, battle.Cell{X: g.sel.X, Y: g.sel.Y},
		plan.SelectionMode, plan.SelectionInnerMark, plan.TargetCode,
		g.st.NativeTargetFlags, g.st.Units,
	)
	if err != nil {
		return nil
	}
	return targets
}

func nativeItemRuntimeRecords(units []*battle.Unit) ([]byte, error) {
	records := make([]byte, 0, len(units)*80)
	for index, unit := range units {
		record, err := battle.NativeItemPanelRecordForUnit(unit)
		if err != nil {
			return nil, fmt.Errorf("runtime unit %d lacks native item record: %w", index, err)
		}
		records = append(records, record...)
	}
	return records, nil
}

func syncNativeItemRuntimeRecord(unit *battle.Unit, record []byte) {
	unit.HP = int(int16(binary.LittleEndian.Uint16(record[0x40:0x42])))
	unit.MP = int(int16(binary.LittleEndian.Uint16(record[0x44:0x46])))
	unit.InventorySlots = make([]int, 8)
	unit.NativeInventoryFlags = make([]int, 8)
	unit.Inventory = unit.Inventory[:0]
	unit.Equipped = unit.Equipped[:0]
	for slot := 0; slot < 8; slot++ {
		flag, item := int(record[0x0a+slot*2]), int(record[0x0b+slot*2])
		unit.NativeInventoryFlags[slot], unit.InventorySlots[slot] = flag, item
		if flag&0x80 == 0 {
			unit.Inventory = append(unit.Inventory, item)
			unit.Equipped = append(unit.Equipped, flag&0x40 != 0)
		}
	}
}

// applyNativeRestoreItem commits types 5/11/13 using the original raw target
// list order and the shared process-lifetime 16-bit RNG state.
func (g *Game) applyNativeRestoreItem(confirmed *battle.Unit) (bool, error) {
	if g == nil || g.st == nil || g.sel == nil || !g.nativeItemTargeting || confirmed == nil {
		return false, nil
	}
	rowOffset, err := battle.NativeItemEffectRowOffset(g.nativeItemTargetID)
	if err != nil || rowOffset+battle.NativeItemEffectRowSize > len(g.nativeItemEffectRows) {
		return false, fmt.Errorf("native item row %d is unavailable", g.nativeItemTargetID)
	}
	row := g.nativeItemEffectRows[rowOffset : rowOffset+battle.NativeItemEffectRowSize]
	plan, err := battle.NativeItemTargetPlanFromRow(row)
	if err != nil {
		return false, err
	}
	targets, err := battle.NativeItemEffectTargets(
		g.st.W, g.st.H, g.sel, confirmed, plan,
		g.st.NativeTargetFlags, g.st.Units,
	)
	if err != nil {
		return false, nil
	}
	sourceUnit := -1
	targetIndices := make([]byte, len(targets))
	for index, unit := range g.st.Units {
		if unit == g.sel {
			sourceUnit = index
		}
		for targetIndex, target := range targets {
			if unit == target {
				targetIndices[targetIndex] = byte(index)
			}
		}
	}
	if sourceUnit < 0 {
		return false, fmt.Errorf("native item source is absent from runtime roster")
	}
	records, err := nativeItemRuntimeRecords(g.st.Units)
	if err != nil {
		return false, err
	}
	amount := binary.LittleEndian.Uint16(row[0x0e:0x10])
	nextRNG := g.nativeRNGState
	if route, ok := battle.NativeItemHPRestoreRouteForType(row[0x0d], amount); ok {
		result, err := battle.ApplyNativeItemHPRestore(
			records, targetIndices, route, g.nativeRNGState,
			sourceUnit, g.nativeItemTargetRawSlot,
		)
		if err != nil {
			return false, err
		}
		nextRNG = result.RNGState
	} else if route, ok := battle.NativeItemMPRestoreRouteForType(row[0x0d], amount); ok {
		result, err := battle.ApplyNativeItemMPRestore(
			records, targetIndices, route, g.nativeRNGState,
			sourceUnit, g.nativeItemTargetRawSlot,
		)
		if err != nil {
			return false, err
		}
		nextRNG = result.RNGState
	} else {
		return false, nil
	}
	for index, unit := range g.st.Units {
		syncNativeItemRuntimeRecord(unit, records[index*80:(index+1)*80])
	}
	g.nativeRNGState = nextRNG
	g.sel.NativeRecordByte5 |= 0x80
	g.sel.HasNativeRecordByte5 = true
	g.sel.Acted = true
	g.nativeItemTargeting = false
	g.nativeItemEffectRows = nil
	g.sel, g.reach, g.moved = nil, nil, false
	return true, nil
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
