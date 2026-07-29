package main

import (
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestComposeNativePreparationFrameUsesRawRosterSelectors(t *testing.T) {
	base := "../../org_game/炎龍騎士團/FLAME2"
	assets, err := fdother.DecodeNativePreparationAssets(
		filepath.Join(base, "FDOTHER.DAT"),
		filepath.Join(base, "FDICON.B24"),
	)
	if err != nil {
		t.Skipf("player-provided original assets are absent: %v", err)
	}
	status, err := battle.LoadNativeItemPanelDataAssets(
		filepath.Join(base, "FDOTHER.DAT"),
		filepath.Join(base, "FDTXT.DAT"),
	)
	if err != nil {
		t.Fatal(err)
	}
	scenario, err := battle.LoadScenario("../../assets/scenarios/ch01.json")
	if err != nil {
		t.Fatal(err)
	}
	units := scenario.PartyUnits(nil)
	if len(units) < 3 {
		t.Fatal("chapter one party lacks three native records")
	}
	ids := make([]int, 3)
	roster := make(map[int]battle.Unit, len(ids))
	for i, unit := range units[:3] {
		ids[i] = unit.Fig
		roster[unit.Fig] = *unit
	}
	g := &Game{
		camp: campaign.NewRunner(&campaign.Campaign{
			Start: "prep",
			Nodes: map[string]*campaign.Node{
				"prep": {Type: "preparation", PartyLimit: 15},
			},
		}),
		nativePreparationUI: &nativePreparationUIAssets{roster: assets, status: status},
		nativeClassUI:       &nativeClassUIAssets{},
		prepIDs:             ids,
		prepSel:             1,
		prepLimit:           15,
		prepSelecting:       true,
		partyDeploy:         map[int]bool{ids[1]: true},
		partyRoster:         roster,
	}
	frame, ok := g.composeNativePreparationFrame()
	if !ok || len(frame) != 320*200 {
		t.Fatalf("native preparation frame unavailable: ok=%v length=%d", ok, len(frame))
	}
	g.partyRoster[ids[1]] = battle.Unit{}
	if _, ok := g.composeNativePreparationFrame(); ok {
		t.Fatal("preparation renderer guessed a missing raw FDICON selector")
	}
}
