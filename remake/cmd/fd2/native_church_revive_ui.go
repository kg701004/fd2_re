package main

import (
	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func (g *Game) nativeReviveFeeForUnit(unit battle.Unit) (int, bool) {
	if !unit.HasNativeRecordClass {
		return 0, false
	}
	classID := int(unit.NativeRecordClass)
	if classID < 0 || classID >= len(g.reviveFeeRates) || unit.Lv < 0 {
		return 0, false
	}
	fee := g.reviveFeeRates[classID] * unit.Lv
	return fee, fee >= 0 && fee <= 0xffff
}

func (g *Game) composeNativeChurchReviveListFrame() ([]byte, bool) {
	a := g.nativeClassUI
	if a == nil || g.churchMode != "revive" || len(g.churchIDs) == 0 {
		return nil, false
	}
	start, visible := campaign.NativeThreeRowWindow(
		len(g.churchIDs), g.churchSel, g.churchVerticalStart,
	)
	if visible == 0 {
		return nil, false
	}
	g.churchVerticalStart = start
	rows := make([]battle.NativeReviveRow, 0, visible)
	for i := 0; i < visible; i++ {
		unit, ok := g.partyRoster[g.churchIDs[start+i]]
		if !ok || !unit.HasNativeIdentity || !unit.HasMapSelectorKey ||
			!unit.HasNativeRecordRace || !unit.HasNativeRecordClass {
			return nil, false
		}
		sprite, err := a.units.SpriteFor(unit.MapSelectorKey, 0, 0)
		if err != nil {
			return nil, false
		}
		fee, ok := g.nativeReviveFeeForUnit(unit)
		if !ok {
			return nil, false
		}
		rows = append(rows, battle.NativeReviveRow{
			Sprite: sprite, NameTextIndex: unit.NativeIdentity + 1,
			RaceTextIndex:  int(unit.NativeRecordRace) + 140,
			ClassTextIndex: int(unit.NativeRecordClass) + 150,
			Fee:            fee,
		})
	}
	background, ok := g.composeNativeChurchSourceFrame()
	if !ok {
		return nil, false
	}
	frame := append([]byte(nil), background...)
	if err := a.panel.BlitOpaqueAt(frame, 320, 5, 112, false); err != nil {
		return nil, false
	}
	assets, err := battle.LoadNativeItemPanelDataAssets(
		nativeFDOTHERPath(), nativeFDTXTPath(),
	)
	if err != nil {
		return nil, false
	}
	if err := battle.RenderNativeReviveRows(
		assets, a.priceCell, rows, g.churchSel-start, frame,
	); err != nil {
		return nil, false
	}
	return frame, true
}

func (g *Game) drawNativeChurchReviveList(screen *ebiten.Image) bool {
	frame, ok := g.composeNativeChurchReviveListFrame()
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
	return true
}

func (g *Game) beginNativeChurchReviveListOpening() bool {
	final, ok := g.composeNativeChurchReviveListFrame()
	if !ok {
		return false
	}
	source, ok := g.composeNativeChurchSourceFrame()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassListOpeningFrames(source, final)
	if err != nil || len(frames) != 6 {
		return false
	}
	g.nativeClassUIJob = &nativeClassUIJob{frames: frames}
	return true
}

func (g *Game) beginNativeChurchReviveListClosing(after func()) bool {
	final, ok := g.composeNativeChurchReviveListFrame()
	if !ok {
		return false
	}
	source, ok := g.composeNativeChurchSourceFrame()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassListClosingFrames(source, final)
	if err != nil || len(frames) != 5 {
		return false
	}
	g.nativeClassUIJob = &nativeClassUIJob{
		frames: frames, restore: source, after: after,
	}
	return true
}

func (g *Game) composeNativeChurchReviveQuestion() ([]byte, bool) {
	a := g.nativeClassUI
	unit, ok := g.partyRoster[g.churchReviveID]
	if a == nil || !ok || !unit.HasNativeIdentity || g.churchReviveFee < 0 {
		return nil, false
	}
	background, ok := g.composeNativeChurchDialogueBase()
	if !ok {
		return nil, false
	}
	frame, err := campaign.ComposeNativeReviveConfirmationQuestion(
		background, a.strings, a.font,
		unit.NativeIdentity+1, g.churchReviveFee,
	)
	return frame, err == nil
}

func (g *Game) composeNativeChurchReviveConfirmation() ([]byte, bool) {
	question, ok := g.composeNativeChurchReviveQuestion()
	if !ok {
		return nil, false
	}
	frame, err := campaign.ComposeNativeConfirmationChoices(
		question, g.nativeClassUI.choices, g.churchSel, g.nativeClassUIPulse/2,
	)
	return frame, err == nil
}

func (g *Game) drawNativeChurchReviveConfirmation(screen *ebiten.Image) bool {
	if g.churchMode != "revive_confirm" {
		return false
	}
	frame, ok := g.composeNativeChurchReviveConfirmation()
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
	return true
}

func (g *Game) beginNativeChurchReviveConfirmationOpening() bool {
	question, ok := g.composeNativeChurchReviveQuestion()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassConfirmationOpeningFrames(
		question, g.nativeClassUI.choices,
	)
	if err != nil || len(frames) != 4 {
		return false
	}
	g.resetNativeClassUIPulse()
	g.nativeClassUIJob = &nativeClassUIJob{frames: frames}
	return true
}

func (g *Game) beginNativeChurchReviveConfirmationClosing(after func()) bool {
	question, ok := g.composeNativeChurchReviveQuestion()
	if !ok {
		return false
	}
	choiceFrames, err := campaign.NativeClassConfirmationClosingFrames(
		question, g.nativeClassUI.choices,
	)
	if err != nil || len(choiceFrames) != 4 {
		return false
	}
	source, ok := g.composeNativeChurchSourceFrame()
	if !ok {
		return false
	}
	dialogue, ok := g.composeNativeChurchDialogueBase()
	if !ok {
		return false
	}
	dialogueFrames, err := campaign.NativeClassListClosingFrames(source, dialogue)
	if err != nil || len(dialogueFrames) != 5 {
		return false
	}
	g.nativeClassUIJob = &nativeClassUIJob{
		frames:  append(choiceFrames, dialogueFrames...),
		restore: source,
		after:   after,
	}
	return true
}

func (g *Game) returnToNativeReviveList() {
	g.churchMode = "revive"
	g.churchIDs = g.churchCandidates("revive")
	g.churchReviveID = -1
	g.churchReviveFee = 0
	g.churchSel = 0
	g.churchVerticalStart = 0
	if len(g.churchIDs) == 0 {
		g.msg = "隊伍中沒有須要復活的！"
		g.returnToNativeChurchMenu()
		return
	}
	g.nativeChurchTextIndex = 589
	g.beginNativeChurchReviveListOpening()
}
