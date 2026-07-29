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
	g := &Game{
		camp: campaign.NewRunner(&campaign.Campaign{
			Start: "prep",
			Nodes: map[string]*campaign.Node{
				"prep": {Type: "preparation", PartyLimit: 15},
			},
		}),
		nativePreparationUI: assets,
		nativeClassUI:       &nativeClassUIAssets{},
		prepIDs:             []int{0, 9, 4},
		prepSel:             1,
		prepLimit:           15,
		prepSelecting:       true,
		partyDeploy:         map[int]bool{9: true},
		partyRoster: map[int]battle.Unit{
			0: {MapSelectorKey: 0, HasMapSelectorKey: true},
			9: {MapSelectorKey: 9, HasMapSelectorKey: true},
			4: {MapSelectorKey: 4, HasMapSelectorKey: true},
		},
	}
	frame, ok := g.composeNativePreparationFrame()
	if !ok || len(frame) != 320*200 {
		t.Fatalf("native preparation frame unavailable: ok=%v length=%d", ok, len(frame))
	}
	g.partyRoster[9] = battle.Unit{}
	if _, ok := g.composeNativePreparationFrame(); ok {
		t.Fatal("preparation renderer guessed a missing raw FDICON selector")
	}
}
