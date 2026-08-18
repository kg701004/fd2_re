package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

// skyKeyGateBeats reproduces ch21_post.json's real shape: an
// "if roster_has_all_items" gate (item_ids 209..214, i.e. 0xd1..0xd6) whose
// then-arm consumes the six items and grants item 100 (the "sky key"),
// followed unconditionally by the join(24)/join(23)/sync_party/set_chapter
// tail that both the success and failure paths share (see doc58's
// 2026-08-18 entries for the disassembly this reproduces).
func skyKeyGateBeats() []campaign.Beat {
	itemID := 100
	chapter := 21
	return []campaign.Beat{
		{
			Op: "if",
			Condition: &campaign.BeatCondition{
				Op:      "roster_has_all_items",
				ItemIDs: []int{209, 210, 211, 212, 213, 214},
			},
			Then: []campaign.Beat{
				{Op: "consume_items", ItemIDs: []int{209, 210, 211, 212, 213, 214}},
				{Op: "grant_item", ItemID: &itemID},
			},
		},
		{Op: "join", CharID: 24},
		{Op: "join", CharID: 23},
		{Op: "sync_party"},
		{Op: "set_chapter", Chapter: &chapter},
	}
}

// skyKeyGateUnits builds 16 runtime slots (the native routine's fixed scan
// width): unit 0 is an own-camp party member with room for the reward,
// units 1..5 each hold one of the six quest items so partyHasItemID's
// slots-0..15 scan (matching native 0x31860/0x24b14) finds every one of
// them regardless of camp, exactly as applyInventoryRecipe's precedent
// already established for this same native routine.
func skyKeyGateUnits(withAllItems bool) []*battle.Unit {
	units := make([]*battle.Unit, 16)
	for i := range units {
		units[i] = &battle.Unit{Camp: battle.Enemy, Fig: 100 + i}
	}
	units[0].Camp, units[0].Fig, units[0].OnField = battle.Own, 0, true
	units[0].Inventory = []int{209}
	units[1].Inventory = []int{210}
	units[2].Inventory = []int{211}
	units[3].Inventory = []int{212}
	units[4].Inventory = []int{213}
	if withAllItems {
		units[5].Inventory = []int{214}
	}
	return units
}

func TestBeatRosterHasAllItemsGrantsSkyKeyOnFullSet(t *testing.T) {
	g := newBeatTestGame(t, skyKeyGateBeats())
	g.partyMembers = map[int]bool{0: true}
	g.st = &battle.State{Units: skyKeyGateUnits(true)}
	g.beatAdvance()

	if g.loadErr != "" {
		t.Fatalf("beats did not complete: err=%q", g.loadErr)
	}
	if !g.partyMembers[24] || !g.partyMembers[23] {
		t.Fatalf("unconditional join tail did not run: party=%#v", g.partyMembers)
	}
	if g.handlerChapter != 21 || g.fade == nil {
		t.Fatalf("unconditional sync_party/set_chapter tail did not run: chapter=%d fade=%#v", g.handlerChapter, g.fade)
	}
	sol := g.partyRoster[0]
	if len(sol.Inventory) != 1 || sol.Inventory[0] != 100 {
		t.Fatalf("full item set did not consume ingredients and grant sky key: %#v", sol.Inventory)
	}
}

func TestBeatRosterHasAllItemsSkipsGrantWhenOneItemMissing(t *testing.T) {
	g := newBeatTestGame(t, skyKeyGateBeats())
	g.partyMembers = map[int]bool{0: true}
	g.st = &battle.State{Units: skyKeyGateUnits(false)} // missing item 214
	g.beatAdvance()

	if g.loadErr != "" {
		t.Fatalf("beats did not complete: err=%q", g.loadErr)
	}
	if !g.partyMembers[24] || !g.partyMembers[23] {
		t.Fatalf("unconditional join tail did not run despite missing ingredient: party=%#v", g.partyMembers)
	}
	if g.handlerChapter != 21 || g.fade == nil {
		t.Fatalf("unconditional sync_party/set_chapter tail did not run: chapter=%d fade=%#v", g.handlerChapter, g.fade)
	}
	sol := g.partyRoster[0]
	if len(sol.Inventory) != 1 || sol.Inventory[0] != 209 {
		t.Fatalf("missing one ingredient must not consume the other five or grant the sky key: %#v", sol.Inventory)
	}
	for _, itemID := range []int{210, 211, 212, 213} {
		found := false
		for _, unit := range g.st.Units {
			for _, held := range unit.Inventory {
				if held == itemID {
					found = true
				}
			}
		}
		if !found {
			t.Fatalf("item %d was consumed despite the recipe being insufficient", itemID)
		}
	}
}
