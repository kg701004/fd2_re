package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestCampaignTownHotelRawRouteReturnTrace(t *testing.T) {
	c := &campaign.Campaign{
		Start: "town_ch02",
		Flags: map[string]bool{},
		Nodes: map[string]*campaign.Node{
			"town_ch02":  {Type: "town", Options: []campaign.Option{{Label: "旅館", To: "hotel_ch02"}}},
			"hotel_ch02": {Type: "hotel", Text: "旅館／整備", Next: "town_ch02"},
		},
	}
	g := &Game{camp: campaign.NewRunner(c), st: &battle.State{}}
	g.stepCampaignMenu(campaign.MenuConfirm)
	g.camp.Advance("opt0")
	g.enterNode()
	if g.camp.NodeID() != "hotel_ch02" || g.st != nil || g.hotelSel != 0 || g.hotelHasRoute {
		t.Fatalf("town→hotel boundary=%q st=%v sel=%d route=%v", g.camp.NodeID(), g.st, g.hotelSel, g.hotelHasRoute)
	}
	for selector, want := range map[byte]uint32{0: 0x2ffa5, 1: 0x30012, 2: 0x301f4, 3: 0x19953} {
		if !g.applyHotelServiceSelection(selector) || !g.hotelHasRoute || g.hotelRoute != (fdother.NativeHotelServiceRoute{Selector: selector, ResourceID: 13, Primary: want, Secondary: map[byte]uint32{3: 0x197e5}[selector]}) {
			t.Fatalf("selector %d route=%#v msg=%q", selector, g.hotelRoute, g.msg)
		}
	}
	prior := g.hotelRoute
	if g.applyHotelServiceSelection(4) || g.hotelRoute != prior {
		t.Fatalf("invalid selector unexpectedly changed route: %#v msg=%q", g.hotelRoute, g.msg)
	}
	g.leaveHotel()
	if g.camp.NodeID() != "town_ch02" {
		t.Fatalf("hotel return node=%q", g.camp.NodeID())
	}
}
