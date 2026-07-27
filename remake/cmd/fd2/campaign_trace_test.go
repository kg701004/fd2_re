package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestCampaignTownPreparationInputTrace(t *testing.T) {
	c := &campaign.Campaign{
		Start: "town_ch02",
		Flags: map[string]bool{},
		Nodes: map[string]*campaign.Node{
			"town_ch02": {
				Type: "town",
				Options: []campaign.Option{
					{Label: "酒店", To: "rumor"},
					{Label: "武器店", To: "shop"},
					{Label: "出戰整備", To: "preparation_ch02"},
				},
			},
			"rumor":            {Type: "story"},
			"shop":             {Type: "shop"},
			"preparation_ch02": {Type: "preparation", Next: "story_ch02_pre"},
			"story_ch02_pre":   {Type: "cutscene", Next: "battle_ch02"},
			"battle_ch02":      {Type: "battle"},
		},
	}
	g := &Game{camp: campaign.NewRunner(c)}
	if got := g.camp.NodeID(); got != "town_ch02" {
		t.Fatalf("start node=%q", got)
	}
	if got, confirm := g.stepCampaignMenu(campaign.MenuDown); got != 1 || confirm {
		t.Fatalf("town down #1=(%d,%v)", got, confirm)
	}
	if got, confirm := g.stepCampaignMenu(campaign.MenuDown); got != 2 || confirm {
		t.Fatalf("town down #2=(%d,%v)", got, confirm)
	}
	selected, confirm := g.stepCampaignMenu(campaign.MenuConfirm)
	if selected != 2 || !confirm {
		t.Fatalf("town confirm=(%d,%v)", selected, confirm)
	}
	if got := g.camp.Advance("opt2"); got != "preparation_ch02" {
		t.Fatalf("town→preparation=%q", got)
	}
	if got := g.camp.NodeID(); got != "preparation_ch02" {
		t.Fatalf("runner node after town=%q", got)
	}
	if got := g.camp.Advance(""); got != "story_ch02_pre" {
		t.Fatalf("preparation→pre handler=%q", got)
	}
	if got := g.camp.Advance(""); got != "battle_ch02" {
		t.Fatalf("pre handler→battle=%q", got)
	}
}
