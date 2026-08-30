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
		partyJoinOrder: make([]int, 17),
		partyRoster:    make(map[int]battle.Unit, 17),
		partyMembers:   make(map[int]bool, 17),
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
	g.partyDeploy[1] = true
	g.prepConfirm = true
	g.restartPreparationSelection()
	if !g.prepSelecting || g.prepConfirm || len(g.partyDeploy) != 0 {
		t.Fatalf(
			"preparation-only retry did not restart zeroed: selecting=%v confirm=%v deploy=%#v",
			g.prepSelecting, g.prepConfirm, g.partyDeploy,
		)
	}
}

func TestPreparationKeepsPersistentRecordZeroOutsideSelectionQuota(t *testing.T) {
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
	if len(g.prepIDs) != 15 || g.prepIDs[0] != 1 || g.prepIDs[14] != 15 {
		t.Fatalf("native selectable records=%v, want persistent records 1..15", g.prepIDs)
	}
	if !g.acceptTownDeparturePrompt() {
		t.Fatal("fixed record zero plus 15 selectable records must bypass 0x318ad")
	}
	g.partyDeploy = map[int]bool{1: true, 2: true}
	members := g.battlePartyMembers()
	if len(members) != 3 || !members[0] || !members[1] || !members[2] {
		t.Fatalf("battle deployment did not restore fixed persistent record zero: %#v", members)
	}
}

// TestForceDeployOverridesPlayerExclusionInSelectionScreen is the regression
// guard for the ch22/23/26-30 "story-forced deploy" gap (91-worklist.md
// 2026-08-30): campaign.Node.ForceDeploy is a remake-only convenience (no RE
// precedent -- see the long comment on that field) that extends the same
// unconditional "always in members" treatment battlePartyMembers() already
// gives partyJoinOrder[0] (the fixed leader) to any other named, already-
// recruited partyRoster member. This proves a player who explicitly
// deselects 希爾法 in the 0x318ad-style manual selection screen (partyDeploy
// records her as unselected) still ends up with her deployed, because
// battle_ch22 authors ForceDeploy:["希爾法"].
func TestForceDeployOverridesPlayerExclusionInSelectionScreen(t *testing.T) {
	g := &Game{
		partyJoinOrder: []int{0, 24, 4},
		partyRoster: map[int]battle.Unit{
			0:  {Fig: 0, Name: "索爾"},
			24: {Fig: 24, Name: "希爾法"},
			4:  {Fig: 4, Name: "亞雷斯"},
		},
		// The manual selection screen ran (roster exceeded prepLimit) and the
		// player picked 亞雷斯 but explicitly left 希爾法 unselected.
		partyDeploy: map[int]bool{24: false, 4: true},
		camp: campaign.NewRunner(&campaign.Campaign{
			Start: "battle_ch22",
			Nodes: map[string]*campaign.Node{
				"battle_ch22": {Type: "battle", Protect: "希爾法", ForceDeploy: []string{"希爾法"}},
			},
		}),
	}
	members := g.battlePartyMembers()
	if !members[24] {
		t.Fatalf("force_deploy did not override player exclusion: %#v", members)
	}
	if !members[0] {
		t.Fatalf("force_deploy regressed the pre-existing fixed-leader inclusion: %#v", members)
	}
	if !members[4] {
		t.Fatalf("force_deploy dropped a genuinely player-selected member: %#v", members)
	}

	// The same guarantee must hold on the auto-bypass path (roster <= cap,
	// so partyDeploy is never populated and battlePartyMembers falls back to
	// partyMembers) for a chapter where the accumulated roster stays small.
	g2 := &Game{
		partyJoinOrder: []int{0, 24},
		partyRoster: map[int]battle.Unit{
			0:  {Fig: 0, Name: "索爾"},
			24: {Fig: 24, Name: "希爾法"},
		},
		partyMembers: map[int]bool{0: true}, // 希爾法 missing from partyMembers despite being recruited
		camp: campaign.NewRunner(&campaign.Campaign{
			Start: "battle_ch22",
			Nodes: map[string]*campaign.Node{
				"battle_ch22": {Type: "battle", Protect: "希爾法", ForceDeploy: []string{"希爾法"}},
			},
		}),
	}
	members2 := g2.battlePartyMembers()
	if !members2[24] {
		t.Fatalf("force_deploy did not apply on the auto-bypass path: %#v", members2)
	}
	// The original g2.partyMembers map must stay untouched (no aliasing
	// mutation of persistent state).
	if g2.partyMembers[24] {
		t.Fatal("battlePartyMembers mutated the persistent partyMembers map in place")
	}
}

// TestForceDeployNeverFabricatesARosterEntry ensures a ForceDeploy name with
// no matching partyRoster unit is a silent no-op, not a synthesized member --
// this is exactly the ch26 亞奇梅吉 case (91-worklist.md 2026-08-30): she is
// never wired into partyRoster by any existing JOIN path, so ForceDeploy
// must not paper over that gap by inventing a phantom id.
func TestForceDeployNeverFabricatesARosterEntry(t *testing.T) {
	g := &Game{
		partyJoinOrder: []int{0},
		partyRoster:    map[int]battle.Unit{0: {Fig: 0, Name: "索爾"}},
		partyMembers:   map[int]bool{0: true},
		camp: campaign.NewRunner(&campaign.Campaign{
			Start: "battle_ch26",
			Nodes: map[string]*campaign.Node{
				"battle_ch26": {Type: "battle", ProtectGuards: []string{"悠妮", "亞奇梅吉"}, ForceDeploy: []string{"悠妮"}},
			},
		}),
	}
	members := g.battlePartyMembers()
	if len(members) != 1 || !members[0] {
		t.Fatalf("ForceDeploy for an unrecruited name fabricated/altered membership: %#v", members)
	}
}

// TestForceDeployedUnitDeathStillTriggersProtectLoss closes the loop end to
// end: force-deploy only guarantees presence, checkResult()'s existing
// Protect wiring (main.go, unchanged by this task) still must fire a real
// "lose" once that guaranteed-present unit actually dies, and must not
// misfire while she is alive.
func TestForceDeployedUnitDeathStillTriggersProtectLoss(t *testing.T) {
	newState := func(silfaHP int) *battle.State {
		return &battle.State{Units: []*battle.Unit{
			{Fig: 0, Name: "索爾", Camp: battle.Own, HP: 10},
			{Fig: 24, Name: "希爾法", Camp: battle.Own, HP: silfaHP},
			{Fig: 99, Camp: battle.Enemy, HP: 10},
		}}
	}
	node := &campaign.Node{Type: "battle", Protect: "希爾法", ForceDeploy: []string{"希爾法"}}
	camp := campaign.NewRunner(&campaign.Campaign{
		Start: "battle_ch22",
		Nodes: map[string]*campaign.Node{"battle_ch22": node},
	})

	dead := &Game{st: newState(0), sc: &battle.Scenario{}, camp: camp}
	dead.checkResult()
	if dead.result != "lose" {
		t.Fatalf("希爾法 death did not trigger the Protect loss condition: result=%q", dead.result)
	}

	alive := &Game{st: newState(10), sc: &battle.Scenario{}, camp: camp}
	alive.checkResult()
	if alive.result != "" {
		t.Fatalf("Protect misfired while 希爾法 is alive and an enemy remains: result=%q", alive.result)
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
