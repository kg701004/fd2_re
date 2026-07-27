package main

import (
	"math/rand"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestCampaignTownChurchClassChangeReturnTrace(t *testing.T) {
	c := &campaign.Campaign{
		Start: "town_ch02",
		Flags: map[string]bool{},
		Nodes: map[string]*campaign.Node{
			"town_ch02": {Type: "town", Options: []campaign.Option{
				{Label: "武器店", To: "shop"},
				{Label: "教會", To: "church_ch02"},
			}},
			"shop":        {Type: "shop", Next: "town_ch02"},
			"church_ch02": {Type: "church", Next: "town_ch02"},
		},
	}
	u := battle.Unit{Name: "悠妮", Portrait: 9, BattleFig: 9, ClassID: 5, Lv: 20, Exp: 31, AP: 20, DP: 18, DX: 12, MV: 5, Inventory: []int{0x5a}, Equipped: []bool{true}, InventorySlots: []int{0x5a}}
	optionalTarget, specialTarget := 0x3b, 0x34
	g := &Game{
		camp:           campaign.NewRunner(c),
		partyRoster:    map[int]battle.Unit{0: u},
		partyMembers:   map[int]bool{0: true},
		partyJoinOrder: []int{0},
		classChangeTable: campaign.ClassChangeTable{
			Current: map[int]campaign.ClassChangeCurrent{9: {
				Portrait: 9, DefaultTarget: 0x29, ItemID: 0x58,
				OptionalTarget: &optionalTarget, SpecialItem: 0x5a, SpecialTarget: &specialTarget,
			}},
			Targets: map[int]campaign.ClassChangeTarget{
				0x29: {Portrait: 0x29, ClassID: 13},
				0x3b: {Portrait: 0x3b, ClassID: 22},
				0x34: {Portrait: 0x34, ClassID: 21, MobilityIncrement: 2},
			},
		},
		classChangeGrowth: map[int]campaign.ClassChangeGrowth{0x34: {AP: [2]int{10, 11}, DP: [2]int{20, 21}, DX: [2]int{30, 31}, HP: [2]int{40, 41}, MP: [2]int{50, 51}}},
		rng:               rand.New(rand.NewSource(1)),
	}
	g.stepCampaignMenu(campaign.MenuDown)
	selected, confirm := g.stepCampaignMenu(campaign.MenuConfirm)
	if selected != 1 || !confirm || g.camp.Advance("opt1") != "church_ch02" {
		t.Fatalf("town→church trace=(%d,%v,%q)", selected, confirm, g.camp.NodeID())
	}
	target, ok := campaign.NativeClassChangeTarget(&u, g.classChangeTable)
	if !ok || target.Branch != "special" || target.Portrait != 0x34 {
		t.Fatalf("native target priority=%+v ok=%v", target, ok)
	}
	g.churchMode, g.churchClassID = "class_confirm", 0
	g.churchBranches = []campaign.ClassChangeBranch{target}
	if !g.applyChurchClassChange(0) {
		t.Fatalf("class change failed: msg=%q", g.msg)
	}
	changed := g.partyRoster[0]
	if changed.Portrait != 0x34 || changed.ClassID != 21 || changed.MV != 7 || changed.Exp != 0 || len(changed.Inventory) != 0 {
		t.Fatalf("class mutation=%#v", changed)
	}
	g.leaveChurch()
	if got := g.camp.NodeID(); got != "town_ch02" {
		t.Fatalf("church class return node=%q, want town_ch02", got)
	}
}
