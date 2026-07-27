package main

import (
	"os"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func TestNativeChurchPanelLifecycleMatches17AEDSchedules(t *testing.T) {
	source := make([]byte, 320*200)
	panel := make([]byte, 320*200)
	for y := 7; y < 196; y++ {
		for x := 5; x < 315; x++ {
			panel[y*320+x] = 9
		}
	}
	opening, err := nativeChurchPanelFrames(source, panel, true)
	if err != nil || len(opening) != 12 {
		t.Fatalf("opening frames=%d err=%v", len(opening), err)
	}
	closing, err := nativeChurchPanelFrames(source, panel, false)
	if err != nil || len(closing) != 12 {
		t.Fatalf("closing frames=%d err=%v", len(closing), err)
	}
	if opening[0][7*320+5] != 9 || opening[11][7*320+5] != 9 {
		t.Fatal("left panel was not composed in opening schedule")
	}
	transition, err := nativeChurchBottomPanelFrame(source, panel, 6)
	if err != nil {
		t.Fatal(err)
	}
	if transition[190*320+5] != 9 || transition[189*320+5] != 0 {
		t.Fatal("bottom step6 did not land at y190")
	}
}

func TestNativeChurchStatusUsesPlayerOriginalAssets(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2/"
	for _, name := range []string{"FDOTHER.DAT", "FDTXT.DAT", "DATO.DAT"} {
		if _, err := os.Stat(base + name); err != nil {
			t.Skip("player-provided original archives are absent")
		}
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", base+"FDOTHER.DAT")
	t.Setenv("FD2_ORIGINAL_FDTXT", base+"FDTXT.DAT")
	t.Setenv("FD2_ORIGINAL_DATO", base+"DATO.DAT")
	assets, err := loadNativeClassUIAssets()
	if err != nil {
		t.Fatal(err)
	}
	unit := *nativeItemPanelTestUnit()
	unit.NativeIdentity, unit.HasNativeIdentity = 9, true
	unit.MapSelectorKey, unit.HasMapSelectorKey = 9, true
	unit.NativeCommandMask = [5]byte{1}
	g := &Game{
		nativeClassUI:         assets,
		nativeChurchTextIndex: 585,
		partyRoster:           map[int]battle.Unit{9: unit},
		churchMode:            "status_roster",
		churchIDs:             []int{9},
		churchStatusID:        -1,
		nativeCommandBook:     []battle.NativeCommandRecord{{ID: 0, MPCost: 2}},
	}
	status, commands, ok := g.prepareNativeChurchStatus(9)
	if !ok || len(status) != 320*200 || len(commands) != 320*200 {
		t.Fatalf("status=%d commands=%d ok=%v", len(status), len(commands), ok)
	}
	if !g.beginNativeChurchStatus(9) || g.churchMode != "status_view" ||
		len(g.nativeClassUIJob.frames) != 12 {
		t.Fatal("native status twelve-frame opening did not start")
	}
	g.nativeClassUIJob = nil
	if !g.beginNativeChurchStatusCommandTransition() ||
		len(g.nativeClassUIJob.frames) != 14 {
		t.Fatal("native status-to-command fourteen-frame transition did not start")
	}
	g.nativeClassUIJob = nil
	g.churchMode = "status_commands"
	g.closeNativeChurchStatus(g.churchCommandPanel)
	if g.nativeClassUIJob == nil || len(g.nativeClassUIJob.frames) != 12 ||
		len(g.nativeClassUIJob.restore) != 320*200 {
		t.Fatal("native command panel twelve-frame closing did not start")
	}
}
