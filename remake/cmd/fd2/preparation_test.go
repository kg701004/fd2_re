package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestPreparationStartsAtRecordPromptAndDoesNotPreselectRoster(t *testing.T) {
	g := &Game{
		partyJoinOrder: []int{0, 9, 4, 30},
		partyRoster: map[int]battle.Unit{
			0: {Fig: 0, Name: "索爾"}, 9: {Fig: 9, Name: "悠妮"},
			4: {Fig: 4, Name: "亞雷斯"}, 30: {Fig: 30, Name: "蓋亞"},
		},
		partyMembers: map[int]bool{0: true, 9: true, 4: true, 30: true},
	}
	g.setupPreparation(&campaign.Node{Type: "preparation", PartyLimit: 19})
	if g.preparationSelected() != 0 || len(g.partyDeploy) != 0 {
		t.Fatalf("0x318c7 must clear selection flags: selected=%d deploy=%v", g.preparationSelected(), g.partyDeploy)
	}
	if len(g.partyMembers) != 4 || !g.partyMembers[30] {
		t.Fatalf("preparation changed permanent JOIN roster: %#v", g.partyMembers)
	}
	if g.prepSelecting || g.prepConfirm || g.prepConfirmSel != 0 {
		t.Fatalf("preparation skipped initial record prompt: selecting=%v confirm=%v choice=%d", g.prepSelecting, g.prepConfirm, g.prepConfirmSel)
	}
	if !g.acceptTownDeparturePrompt() || g.prepSelecting {
		t.Fatal("roster below native cap did not bypass 0x318ad")
	}

	sc := &battle.Scenario{Party: []battle.PartyMember{{Fig: 0, Name: "索爾"}, {Fig: 9, Name: "悠妮"}, {Fig: 4, Name: "亞雷斯"}}}
	filterScenarioParty(sc, map[int]bool{0: true, 4: true})
	if len(sc.Party) != 2 || sc.Party[0].Fig != 0 || sc.Party[1].Fig != 4 {
		t.Fatalf("battle deployment filter=%#v", sc.Party)
	}
}

func TestPreparationRecordPromptEntersZeroedSelectionOnlyAboveCap(t *testing.T) {
	g := &Game{
		partyJoinOrder: make([]int, 16),
		partyRoster:    make(map[int]battle.Unit, 16),
		partyMembers:   make(map[int]bool, 16),
	}
	for id := range g.partyJoinOrder {
		g.partyJoinOrder[id] = id
		g.partyRoster[id] = battle.Unit{Fig: id}
		g.partyMembers[id] = true
	}
	g.setupPreparation(&campaign.Node{Type: "preparation", PartyLimit: 15})
	if g.acceptTownDeparturePrompt() || !g.prepSelecting {
		t.Fatal("roster above cap bypassed native 0x318ad selection")
	}
	if g.preparationSelected() != 0 || len(g.partyDeploy) != 0 {
		t.Fatalf("selection did not start zeroed: %#v", g.partyDeploy)
	}
	g.partyDeploy[0] = true
	g.prepConfirm = true
	g.restartPreparationSelection()
	if !g.prepSelecting || g.prepConfirm || len(g.partyDeploy) != 0 {
		t.Fatalf(
			"preparation-only retry did not restart zeroed: selecting=%v confirm=%v deploy=%#v",
			g.prepSelecting, g.prepConfirm, g.partyDeploy,
		)
	}
}

func TestPreparationPromptSourcePreservesTownAndClearsStandalone(t *testing.T) {
	source := make([]byte, 320*200)
	for i := range source {
		source[i] = 7
	}
	g := &Game{
		prepPromptSource: append([]byte(nil), source...),
		partyRoster:      map[int]battle.Unit{},
	}
	g.setupPreparation(&campaign.Node{
		Type: "preparation", Cancel: "town", PartyLimit: 15,
	})
	if len(g.prepPromptSource) != 320*200 || g.prepPromptSource[0] != 7 {
		t.Fatal("town-backed preparation discarded its source frame")
	}
	g.setupPreparation(&campaign.Node{Type: "preparation", PartyLimit: 15})
	if len(g.prepPromptSource) != 320*200 || g.prepPromptSource[0] != 0 {
		t.Fatal("standalone preparation did not use 0x2cc04 black source")
	}
}
