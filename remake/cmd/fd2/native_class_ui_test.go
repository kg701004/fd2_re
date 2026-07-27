package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestDrawNativeClassListUsesPlayerOriginalAssets(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2"
	fdotherPath := filepath.Join(base, "FDOTHER.DAT")
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", fdotherPath)
	t.Setenv("FD2_ORIGINAL_FDTXT", filepath.Join(base, "FDTXT.DAT"))
	assets, err := loadNativeClassUIAssets()
	if err != nil {
		t.Fatal(err)
	}
	special := 0x34
	g := &Game{
		nativeClassUI: assets,
		churchMode:    "class",
		churchIDs:     []int{9},
		partyRoster: map[int]battle.Unit{
			9: {
				Name: "悠妮", Portrait: 9, ClassID: 5,
				NativeIdentity: 9, HasNativeIdentity: true,
				MapSelectorKey: 9, HasMapSelectorKey: true,
				Inventory: []int{0x5a},
			},
			0: {
				Name: "索爾", Portrait: 0, ClassID: 0,
				NativeIdentity: 0, HasNativeIdentity: true,
				MapSelectorKey: 0, HasMapSelectorKey: true,
			},
		},
		classChangeTable: campaign.ClassChangeTable{
			Current: map[int]campaign.ClassChangeCurrent{9: {
				Portrait: 9, DefaultTarget: 0x29, SpecialItem: 0x5a, SpecialTarget: &special,
			}},
			Targets: map[int]campaign.ClassChangeTarget{
				0x29: {Portrait: 0x29, ClassID: 13},
				0x34: {Portrait: 0x34, ClassID: 21},
			},
		},
		nativeChurchTextIndex: 585,
	}
	screen := ebiten.NewImage(640, 400)
	if !g.drawNativeClassList(screen) {
		t.Fatal("native class list unexpectedly fell back")
	}
	if !g.beginNativeClassListOpening() || len(g.nativeClassUIJob.frames) != 6 {
		t.Fatal("native six-frame class list opening unexpectedly fell back")
	}
	g.nativeClassUIJob = nil
	if !g.beginNativeClassListClosing(nil) || len(g.nativeClassUIJob.frames) != 5 ||
		len(g.nativeClassUIJob.restore) != 320*200 {
		t.Fatal("native five-frame class list closing and source restore unexpectedly fell back")
	}
	g.nativeClassUIJob = nil
	g.churchMode, g.churchClassID, g.churchSel = "class_confirm", 9, 0
	if !g.drawNativeClassConfirmation(screen) {
		t.Fatal("native class confirmation unexpectedly fell back")
	}
	if !g.beginNativeClassConfirmationOpening() || len(g.nativeClassUIJob.frames) != 4 {
		t.Fatal("native four-frame confirmation opening unexpectedly fell back")
	}
	g.nativeClassUIJob = nil
	if !g.beginNativeClassConfirmationClosing(nil) || len(g.nativeClassUIJob.frames) != 9 ||
		len(g.nativeClassUIJob.restore) != 320*200 {
		t.Fatal("native confirmation choice/dialogue closing and source restore unexpectedly fell back")
	}
	g.nativeClassUIJob = nil
	g.churchMode, g.churchIDs, g.churchSel = "status_roster", []int{9}, 0
	if !g.drawNativeChurchRoster(screen) {
		t.Fatal("native two-column church roster unexpectedly fell back")
	}
	if !g.beginNativeChurchRosterOpening() || len(g.nativeClassUIJob.frames) != 6 {
		t.Fatal("native six-frame church roster opening unexpectedly fell back")
	}
	g.nativeClassUIJob = nil
	if !g.beginNativeChurchRosterClosing(nil) || len(g.nativeClassUIJob.frames) != 5 ||
		len(g.nativeClassUIJob.restore) != 320*200 {
		t.Fatal("native five-frame church roster closing and source restore unexpectedly fell back")
	}
	g.nativeClassUIJob = nil
	g.churchMode, g.churchSel = "transfer_item", 0
	g.churchTransferSource, g.churchTransferItems = 9, []int{0}
	g.nativeChurchTextIndex = 512
	if !g.drawNativeChurchTransferItem(screen) {
		t.Fatal("native transfer item list unexpectedly fell back")
	}
	if !g.beginNativeChurchTransferItemOpening() || len(g.nativeClassUIJob.frames) != 6 {
		t.Fatal("native transfer item six-frame opening unexpectedly fell back")
	}
	g.nativeClassUIJob = nil
	if !g.beginNativeChurchTransferItemClosing(nil) ||
		len(g.nativeClassUIJob.frames) != 5 || len(g.nativeClassUIJob.restore) != 320*200 {
		t.Fatal("native transfer item five-frame closing unexpectedly fell back")
	}
}
