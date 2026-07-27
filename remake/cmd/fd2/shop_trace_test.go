package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestCampaignTownShopPurchaseReturnTrace(t *testing.T) {
	c := &campaign.Campaign{
		Start: "town_ch02",
		Flags: map[string]bool{},
		Nodes: map[string]*campaign.Node{
			"town_ch02": {Type: "town", Options: []campaign.Option{
				{Label: "酒店", To: "rumor"},
				{Label: "武器店", To: "shop_ch02_weapon"},
			}},
			"rumor":            {Type: "story"},
			"shop_ch02_weapon": {Type: "shop", Goods: []campaign.Good{{ID: 0x80, Name: "劍", Price: 25}}, Next: "town_ch02"},
		},
	}
	u := battle.Unit{Name: "索爾", Inventory: []int{1}}
	g := &Game{
		camp:           campaign.NewRunner(c),
		gold:           30,
		partyRoster:    map[int]battle.Unit{0: u},
		partyMembers:   map[int]bool{0: true},
		partyJoinOrder: []int{0},
	}
	// town options: down→weapon shop, enter→opt1.
	g.stepCampaignMenu(campaign.MenuDown)
	selected, confirm := g.stepCampaignMenu(campaign.MenuConfirm)
	if selected != 1 || !confirm || g.camp.Advance("opt1") != "shop_ch02_weapon" {
		t.Fatalf("town→shop trace=(%d,%v,%q)", selected, confirm, g.camp.NodeID())
	}
	good := g.camp.ShopGoods()[0]
	slot, err := campaign.ReserveGood(g.gold, &u, good)
	if err != nil || slot != 1 || len(u.Inventory) != 2 || g.gold != 30 {
		t.Fatalf("reserve changed purchase boundary slot=%d err=%v gold=%d inv=%v", slot, err, g.gold, u.Inventory)
	}
	g.gold = campaign.FinalizeGood(g.gold, good)
	g.partyRoster[0] = u
	if g.gold != 5 {
		t.Fatalf("finalized gold=%d, want 5", g.gold)
	}
	g.leaveShop()
	if got := g.camp.NodeID(); got != "town_ch02" {
		t.Fatalf("shop return node=%q, want town_ch02", got)
	}
	if got := g.partyRoster[0].Inventory; len(got) != 2 || got[1] != 0x80 {
		t.Fatalf("purchased inventory=%v", got)
	}
}
