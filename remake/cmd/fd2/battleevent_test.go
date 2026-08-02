package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func driveNativeBattleIntro(t *testing.T, g *Game) int {
	t.Helper()
	frames := 0
	for g.spawnIntroTransition != nil {
		frames++
		g.spawnIntroTransition.drawn = true
		g.stepNativeSpawnIntro()
		if frames > 12 {
			t.Fatal("native battle intro exceeded twelve presentation passes")
		}
	}
	if frames != 12 || g.actJob == nil {
		t.Fatalf("native battle intro frames=%d acting=%v, want 12 then acting", frames, g.actJob != nil)
	}
	return frames
}

func driveNativeBattleActing(t *testing.T, g *Game) {
	t.Helper()
	for ticks := 0; g.actJob != nil; ticks++ {
		if ticks > 1000 {
			t.Fatal("native battle following acting did not complete")
		}
		g.stepActJob()
	}
}

func TestNativeBattleIntroCallRequiresExactEventCallerProvenance(t *testing.T) {
	gate, eventID := 0, 1
	action := battle.Action{
		Type: "spawn_group", Groups: []int{4}, Camp: "enemy", NativeEventID: &eventID,
		NativeSpawns: []battle.NativeSpawnCall{{
			Group: 4, Via: "spawn_group_with_intro", Source: "0x342ce", RawPlacementGate: &gate,
			FollowingActing: &battle.NativeFollowingActing{Resource: 3, Source: "0x342e7"},
		}},
	}
	if call, ok, err := nativeBattleIntroCall(action); err != nil || !ok || call.Group != 4 {
		t.Fatalf("exact event1 provenance rejected: call=%#v ok=%v err=%v", call, ok, err)
	}
	action.NativeSpawns[0].Source = "0x342cf"
	if _, _, err := nativeBattleIntroCall(action); err == nil {
		t.Fatal("changed spawn caller address was accepted")
	}
	action.NativeSpawns[0].Source = "0x342ce"
	action.NativeSpawns[0].FollowingActing.Resource = 4
	if _, _, err := nativeBattleIntroCall(action); err == nil {
		t.Fatal("changed following ACTING resource was accepted")
	}
}

func TestChapter1GlobalIntroEventsPresentThenRunExactFollowingActing(t *testing.T) {
	const originalBase = "../../../org_game/炎龍騎士團/FLAME2"
	fdotherPath := filepath.Join(originalBase, "FDOTHER.DAT")
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", fdotherPath)

	st, err := battle.Load(assetPath("assets/maps/map0/map0_units.json"))
	if err != nil {
		t.Fatal(err)
	}
	sc, err := battle.LoadScenario(assetPath("assets/scenarios/ch01.json"))
	if err != nil {
		t.Fatal(err)
	}
	sc.Setup(st)
	g := &Game{st: st, sc: sc, sfxSpawnIntro: []byte{1}}
	if err := g.bindNativeFutureItemRows(st); err != nil {
		t.Fatal(err)
	}
	if err := g.loadMap("assets/maps/map0"); err != nil {
		t.Fatal(err)
	}

	// Event0 establishes the exact 14-slot frontier consumed by ACTING(3).
	st.Turn = 3
	g.finishTurn()
	if len(g.dialog) != 1 || len(st.Units) != 14 {
		t.Fatalf("turn3 frontier/dialogue units=%d dialog=%#v", len(st.Units), g.dialog)
	}
	g.dialog = nil
	g.advanceBattleEvent()
	if st.Turn != 4 || g.battleEvent != nil {
		t.Fatalf("turn3 completion turn=%d event=%#v", st.Turn, g.battleEvent)
	}
	st.NativeMapCycleState.Idle, st.NativeMapCycleState.Moving = 2, 3
	st.NativeTerrainPhaseState.Phase = 5
	st.NativeTerrainFlipState.Value = 1
	st.NativeUnitPixelShiftState.Value = 1

	// A missing editable acting resource must fail before constructor state,
	// selector cache, or the turn continuation is published.
	badScenario, err := battle.LoadScenario(assetPath("assets/scenarios/ch01.json"))
	if err != nil {
		t.Fatal(err)
	}
	badScenario.NativeActingResources = "assets/cutscenes/acting/missing.json"
	g.sc = badScenario
	beforeRoster, beforeCache := len(st.Roster), st.NativeMapSelectorCache
	g.finishTurn()
	if g.loadErr == "" || len(st.Units) != 14 || len(st.Roster) != beforeRoster ||
		st.NativeMapSelectorCache != beforeCache || st.Turn != 4 || g.battleEvent != nil {
		t.Fatalf(
			"failed intro mutated state: err=%q units=%d roster=%d/%d cache_same=%v turn=%d event=%#v",
			g.loadErr, len(st.Units), len(st.Roster), beforeRoster,
			st.NativeMapSelectorCache == beforeCache, st.Turn, g.battleEvent,
		)
	}
	g.loadErr = ""
	sc, err = battle.LoadScenario(assetPath("assets/scenarios/ch01.json"))
	if err != nil {
		t.Fatal(err)
	}
	g.sc = sc

	// Event1 constructs group4 before pass0, presents exactly 12 frames, then
	// executes the independent 0x342E7 ACTING(3) on slots14..17.
	g.finishTurn()
	if len(st.Units) != 18 || g.spawnIntroTransition == nil || g.actJob != nil || st.Turn != 4 {
		t.Fatalf("event1 start units=%d intro=%v acting=%v turn=%d", len(st.Units), g.spawnIntroTransition != nil, g.actJob != nil, st.Turn)
	}
	if st.NativeMapCycleState.Idle != 2 || st.NativeMapCycleState.Moving != 3 ||
		st.NativeTerrainPhaseState.Phase != 5 || st.NativeTerrainFlipState.Value != 1 ||
		st.NativeUnitPixelShiftState.Value != 1 {
		t.Fatalf("event1 reset battle animation phase: cycle=%#v terrain=%#v flip=%#v shift=%#v",
			st.NativeMapCycleState, st.NativeTerrainPhaseState,
			st.NativeTerrainFlipState, st.NativeUnitPixelShiftState)
	}
	driveNativeBattleIntro(t, g)
	before3 := [4][2]int{}
	for i := range before3 {
		before3[i] = [2]int{st.Units[14+i].X, st.Units[14+i].Y}
	}
	driveNativeBattleActing(t, g)
	want3 := [4][2]int{{-4, -2}, {-4, -2}, {-2, -4}, {-4, -2}}
	for i, delta := range want3 {
		u := st.Units[14+i]
		if u.X != before3[i][0]+delta[0] || u.Y != before3[i][1]+delta[1] {
			t.Fatalf("ACTING(3) slot%d=(%d,%d), start=%v delta=%v", 14+i, u.X, u.Y, before3[i], delta)
		}
	}
	if st.Turn != 5 || g.battleEvent != nil {
		t.Fatalf("event1 completion turn=%d event=%#v", st.Turn, g.battleEvent)
	}

	// Event2 repeats the same presentation boundary, then ACTING(4), and only
	// after that exposes the authored boss dialogue.
	g.finishTurn()
	if len(st.Units) != 23 || g.spawnIntroTransition == nil || st.Turn != 5 {
		t.Fatalf("event2 start units=%d intro=%v turn=%d", len(st.Units), g.spawnIntroTransition != nil, st.Turn)
	}
	driveNativeBattleIntro(t, g)
	before4 := [5][2]int{}
	for i := range before4 {
		before4[i] = [2]int{st.Units[18+i].X, st.Units[18+i].Y}
	}
	driveNativeBattleActing(t, g)
	want4 := [5][2]int{{1, -1}, {0, -1}, {1, 0}, {0, -1}, {1, 0}}
	for i, delta := range want4 {
		u := st.Units[18+i]
		if u.X != before4[i][0]+delta[0] || u.Y != before4[i][1]+delta[1] {
			t.Fatalf("ACTING(4) slot%d=(%d,%d), start=%v delta=%v", 18+i, u.X, u.Y, before4[i], delta)
		}
	}
	if len(g.dialog) != 1 || g.dialog[0].Speaker != 71 || st.Turn != 5 || g.battleEvent == nil {
		t.Fatalf("event2 following dialogue=%#v turn=%d event=%#v", g.dialog, st.Turn, g.battleEvent)
	}
	g.dialog = nil
	g.advanceBattleEvent()
	if st.Turn != 6 || g.battleEvent != nil {
		t.Fatalf("event2 completion turn=%d event=%#v", st.Turn, g.battleEvent)
	}
}

func TestChapter3Turn3BattleEventBlocksTurnUntilOriginalSequenceCompletes(t *testing.T) {
	st, err := battle.Load(assetPath("assets/maps/map2/map2_units.json"))
	if err != nil {
		t.Fatal(err)
	}
	sc, err := battle.LoadScenario(assetPath("assets/scenarios/ch03.json"))
	if err != nil {
		t.Fatal(err)
	}
	sc.Setup(st)
	st.Turn = 3
	st.Units[0].Poisoned, st.Units[0].PoisonTurns = true, 2

	g := &Game{m: &MapData{W: 40, H: 40, TileW: 24, TileH: 24}, st: st, sc: sc}
	if err := g.bindNativeFutureItemRows(st); err != nil {
		t.Fatal(err)
	}
	g.finishTurn()
	if len(st.Units) != 27 || g.battleEvent == nil || g.camPan == nil {
		t.Fatalf("event did not execute SPAWN then block on first PAN: units=%d run=%#v pan=%#v", len(st.Units), g.battleEvent, g.camPan)
	}
	if st.Turn != 3 || st.Units[0].PoisonTurns != 2 {
		t.Fatalf("turn/status advanced before staging: turn=%d poison=%d", st.Turn, st.Units[0].PoisonTurns)
	}
	g.finishTurn() // re-entry while blocked must be a no-op
	if st.Turn != 3 || len(st.Units) != 27 {
		t.Fatalf("finishTurn re-entry duplicated event: turn=%d units=%d", st.Turn, len(st.Units))
	}

	for i := 0; i < 3; i++ {
		g.stepCamPan()
	}
	if g.camX != 72 || g.camY != 0 || g.camPan != nil || g.battleEventDelay != 48 {
		t.Fatalf("first PAN/delay = cam(%v,%v) pan=%#v delay=%d, want (72,0)/nil/48", g.camX, g.camY, g.camPan, g.battleEventDelay)
	}
	for i := 0; i < 47; i++ {
		g.stepBattleEventDelay()
	}
	if g.battleEventDelay != 1 || g.camPan != nil || st.Turn != 3 {
		t.Fatalf("800ms wait ended early: delay=%d pan=%#v turn=%d", g.battleEventDelay, g.camPan, st.Turn)
	}
	g.stepBattleEventDelay()
	if g.camPan == nil || g.camPan.toX != 72 || g.camPan.toY != 408 {
		t.Fatalf("second PAN target=%#v, want pixel (72,408)", g.camPan)
	}
	for i := 0; i < 17; i++ {
		g.stepCamPan()
	}
	if g.camX != 72 || g.camY != 408 || g.camPan != nil || g.battleEventDelay != 12 {
		t.Fatalf("second PAN/delay = cam(%v,%v) pan=%#v delay=%d, want (72,408)/nil/12", g.camX, g.camY, g.camPan, g.battleEventDelay)
	}
	for i := 0; i < 12; i++ {
		g.stepBattleEventDelay()
	}
	if len(g.dialog) != 1 || g.dialog[0].Speaker != 77 || g.dialog[0].Text != "鐵諾,你果然很耐命!怪不得頭子一定要我親自來看看....不過,你的好運也到此為止了!" {
		t.Fatalf("first authored dialogue played out of order: %#v", g.dialog)
	}
	if st.Turn != 3 || st.Units[0].PoisonTurns != 2 {
		t.Fatalf("turn/status advanced before dialogue completion: turn=%d poison=%d", st.Turn, st.Units[0].PoisonTurns)
	}

	wantSpeakers := []int{77, 2, 77, 8, 2, 8, 77}
	for i, speaker := range wantSpeakers {
		if len(g.dialog) != 1 || g.dialog[0].Speaker != speaker {
			t.Fatalf("dialogue %d speaker=%#v, want %d", i, g.dialog, speaker)
		}
		g.dialog = nil
		g.advanceBattleEvent()
	}
	if g.battleEvent != nil || st.Turn != 4 || st.Units[0].PoisonTurns != 1 {
		t.Fatalf("sequence completion = run=%#v turn=%d poison=%d, want nil/4/1", g.battleEvent, st.Turn, st.Units[0].PoisonTurns)
	}
}

func TestBattleEventNativeSpawnFailureDoesNotAdvanceTurnContinuation(t *testing.T) {
	gate, eventID := 1, 3
	st := &battle.State{Turn: 6}
	sc := &battle.Scenario{RuntimeAppendGroups: true}
	action := battle.Action{
		Type: "spawn_group", Groups: []int{6}, NativeEventID: &eventID,
		NativeSpawns: []battle.NativeSpawnCall{{
			Group: 6, Via: "spawn_group", Source: "0x34397", RawPlacementGate: &gate,
		}},
	}
	continued := false
	g := &Game{st: st, sc: sc}
	g.startBattleEvent([]battle.Action{action}, func() { continued = true })

	if g.loadErr == "" || continued || st.Turn != 6 || g.battleEvent != nil {
		t.Fatalf(
			"失敗事件仍前進：err=%q continued=%v turn=%d run=%#v",
			g.loadErr, continued, st.Turn, g.battleEvent,
		)
	}
}

func triggerChapter7Event26(t *testing.T, g *Game) {
	t.Helper()
	if g == nil || g.st == nil || len(g.st.Units) <= 27 {
		t.Fatal("chapter7 event26 runtime frontier is absent")
	}
	trigger := g.st.Units[0]
	if trigger == nil || !trigger.HasNativeRecordByte6 || trigger.NativeRecordByte6 == 0 {
		t.Fatalf("chapter7 event26 trigger=%#v", trigger)
	}
	trigger.SetMapPlacement(10, 13, 0)
	done := false
	g.walk = &walkAnim{
		u: trigger,
		path: []battle.Cell{
			{X: 10, Y: 13},
			{X: 9, Y: 13},
		},
		then: func() { done = true },
	}
	for steps := 0; g.walk != nil && steps < 8; steps++ {
		g.stepBattleWalk()
	}
	if !done || g.walk != nil || g.loadErr != "" || g.st.NativeEventState[16] != 1 {
		t.Fatalf(
			"event26 done=%v walk=%v err=%q state16=%d",
			done, g.walk != nil, g.loadErr, g.st.NativeEventState[16],
		)
	}
	for index := 9; index <= 27; index++ {
		unit := g.st.Units[index]
		if unit == nil || !unit.HasNativeRecordByte34 || unit.NativeRecordByte34&0x0f != 0 {
			t.Fatalf("event26 unit%d=%#v", index, unit)
		}
	}
}

func TestChapter7Event26RejectsWrongTriggerProvenance(t *testing.T) {
	tests := []struct {
		name        string
		triggerSlot int
		from        battle.Cell
		to          battle.Cell
	}{
		{
			name:        "raw_byte6_zero",
			triggerSlot: 9,
			from:        battle.Cell{X: 10, Y: 13},
			to:          battle.Cell{X: 9, Y: 13},
		},
		{
			name:        "outside_event_cells",
			triggerSlot: 0,
			from:        battle.Cell{X: 8, Y: 13},
			to:          battle.Cell{X: 7, Y: 13},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			g := &Game{}
			if err := g.loadMap("assets/maps/map6"); err != nil {
				t.Fatal(err)
			}
			g.resetBattle("assets/maps/map6/map6_units.json", "assets/scenarios/ch07.json")
			if g.loadErr != "" || len(g.st.Units) != 34 {
				t.Fatalf("chapter7 setup err=%q units=%d", g.loadErr, len(g.st.Units))
			}
			trigger := g.st.Units[tc.triggerSlot]
			if trigger == nil || !trigger.HasNativeRecordByte6 {
				t.Fatalf("trigger slot%d=%#v", tc.triggerSlot, trigger)
			}
			if tc.name == "raw_byte6_zero" && trigger.NativeRecordByte6 != 0 {
				t.Fatalf("slot%d raw +6=%d, want zero fixture", tc.triggerSlot, trigger.NativeRecordByte6)
			}
			before := make([]byte, 19)
			for index := 9; index <= 27; index++ {
				unit := g.st.Units[index]
				if unit == nil || !unit.HasNativeRecordByte34 {
					t.Fatalf("slot%d lacks raw +0x34 provenance", index)
				}
				before[index-9] = unit.NativeRecordByte34
			}
			trigger.SetMapPlacement(tc.from.X, tc.from.Y, 0)
			g.walk = &walkAnim{
				u:    trigger,
				path: []battle.Cell{tc.from, tc.to},
			}
			for steps := 0; g.walk != nil && steps < 8; steps++ {
				g.stepBattleWalk()
			}
			if g.walk != nil || g.loadErr != "" || g.st.NativeEventState[16] != 0 {
				t.Fatalf("rejected event26 walk=%v err=%q state16=%d", g.walk != nil, g.loadErr, g.st.NativeEventState[16])
			}
			for index := 9; index <= 27; index++ {
				if got := g.st.Units[index].NativeRecordByte34; got != before[index-9] {
					t.Fatalf("rejected event26 mutated slot%d raw +0x34=%#x, want %#x", index, got, before[index-9])
				}
			}
		})
	}
}

func TestChapter7Event25FailsClosedWithoutFieldEvent26(t *testing.T) {
	g := &Game{}
	if err := g.loadMap("assets/maps/map6"); err != nil {
		t.Fatal(err)
	}
	g.resetBattle("assets/maps/map6/map6_units.json", "assets/scenarios/ch07.json")
	if g.loadErr != "" || len(g.st.Units) != 34 {
		t.Fatalf("chapter7 setup err=%q units=%d", g.loadErr, len(g.st.Units))
	}
	g.st.Turn = 10
	g.finishTurn()
	if g.battleEvent != nil || len(g.st.Units) != 34 ||
		g.st.NativeEventState[16] != 0 || g.st.NativeEventState[17] != 0 || g.st.Turn != 11 {
		t.Fatalf(
			"ungated event25 run=%v units=%d state16=%d state17=%d turn=%d",
			g.battleEvent != nil, len(g.st.Units), g.st.NativeEventState[16],
			g.st.NativeEventState[17], g.st.Turn,
		)
	}
}

func TestChapter7Event25BuildsSlot43ThenCommitsState17(t *testing.T) {
	g := &Game{}
	if err := g.loadMap("assets/maps/map6"); err != nil {
		t.Fatal(err)
	}
	g.resetBattle("assets/maps/map6/map6_units.json", "assets/scenarios/ch07.json")
	if g.loadErr != "" || g.st == nil || g.sc == nil {
		t.Fatalf("chapter7 setup err=%q state=%v scenario=%v", g.loadErr, g.st != nil, g.sc != nil)
	}
	if !g.sc.RuntimeAppendGroups || len(g.st.Units) != 34 || !g.st.PendingGroups[2] {
		t.Fatalf("chapter7 opening units=%d pending=%v runtime_append=%v", len(g.st.Units), g.st.PendingGroups, g.sc.RuntimeAppendGroups)
	}
	triggerChapter7Event26(t, g)
	g.st.Turn = 10
	g.finishTurn()
	if len(g.st.Units) != 44 || g.camPan == nil || g.st.NativeEventState[17] != 0 {
		t.Fatalf("event25 spawn units=%d pan=%v state17=%d", len(g.st.Units), g.camPan != nil, g.st.NativeEventState[17])
	}
	if slot43 := g.st.Units[43]; slot43 == nil || slot43.Group != 2 || slot43.Camp != battle.Ally || slot43.Fig != 12 ||
		!slot43.HasNativeRecordByte5 || slot43.NativeRecordByte5&1 != 0 {
		t.Fatalf("event25 slot43=%#v", slot43)
	}
	for steps := 0; g.camPan != nil && steps < 100; steps++ {
		g.stepCamPan()
	}
	if g.camPan != nil || g.actJob == nil || g.camX != 16*24 || g.camY != 10*24 {
		t.Fatalf("event25 pan/acting pan=%v acting=%v cam=(%v,%v)", g.camPan != nil, g.actJob != nil, g.camX, g.camY)
	}
	driveNativeBattleActing(t, g)
	wantSpeakers := []int{12, -1, 12, -1, 1, 13, 0, 4, 13}
	for i, speaker := range wantSpeakers {
		if len(g.dialog) != 1 || g.dialog[0].Speaker != speaker {
			t.Fatalf("event25 dialogue %d=%#v, want speaker %d", i, g.dialog, speaker)
		}
		if g.st.NativeEventState[17] != 0 {
			t.Fatalf("event25 state17 committed before dialogue %d completed", i)
		}
		g.dialog = nil
		g.advanceBattleEvent()
	}
	if g.battleEvent != nil || g.st.NativeEventState[17] != 1 || g.st.Turn != 11 {
		t.Fatalf("event25 completion run=%v state17=%d turn=%d", g.battleEvent != nil, g.st.NativeEventState[17], g.st.Turn)
	}
}

func TestChapter7PostBranchesOnKeliRawInactiveStateThenEntersTown8(t *testing.T) {
	for _, tc := range []struct {
		name       string
		rawByte5   byte
		wantJoined bool
	}{
		{name: "active_joins", rawByte5: 0, wantJoined: true},
		{name: "inactive_does_not_join", rawByte5: 1, wantJoined: false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			g := &Game{}
			if err := g.loadMap("assets/maps/map6"); err != nil {
				t.Fatal(err)
			}
			g.resetBattle("assets/maps/map6/map6_units.json", "assets/scenarios/ch07.json")
			if g.loadErr != "" || len(g.st.Units) != 34 {
				t.Fatalf("chapter7 setup err=%q units=%d", g.loadErr, len(g.st.Units))
			}
			triggerChapter7Event26(t, g)
			g.st.Turn = 10
			g.finishTurn()
			for steps := 0; g.camPan != nil && steps < 100; steps++ {
				g.stepCamPan()
			}
			driveNativeBattleActing(t, g)
			for g.battleEvent != nil {
				if len(g.dialog) != 0 {
					g.dialog = nil
					g.advanceBattleEvent()
					continue
				}
				g.advanceBattleEvent()
			}
			if g.st.NativeEventState[17] != 1 || len(g.st.Units) != 44 {
				t.Fatalf("event25 boundary state17=%d units=%d", g.st.NativeEventState[17], len(g.st.Units))
			}
			g.st.Units[43].NativeRecordByte5 = tc.rawByte5

			order := []int{0, 4, 9, 30, 1, 8, 2, 10, 13}
			g.partyMembers = make(map[int]bool, len(order))
			for _, id := range order {
				g.partyMembers[id] = true
			}
			g.partyJoinOrder = append([]int(nil), order...)
			if err := g.seedPersistentPartyFromLoadCH(order, g.st.Units[:len(order)]); err != nil {
				t.Fatal(err)
			}
			beats, issues, err := campaign.CompileHandlerBinding(
				assetPath("assets/cutscenes/bindings/ch06_post.json"),
			)
			if err != nil || len(issues) != 0 {
				t.Fatalf("ch06_post compile err=%v issues=%#v", err, issues)
			}
			c := &campaign.Campaign{
				Start: "postbattle_ch07_persist",
				Nodes: map[string]*campaign.Node{
					"postbattle_ch07_persist": {Type: "cutscene", Next: "town_ch08"},
					"town_ch08":               {Type: "town"},
				},
			}
			g.camp = campaign.NewRunner(c)
			g.beats, g.beatIdx, g.storyBG = beats, -1, true
			g.beatAdvance()
			for frame := 0; frame < 10000 && g.camp.NodeID() != "town_ch08"; frame++ {
				if len(g.dialog) != 0 {
					g.dialog = nil
					g.beatAdvance()
				}
				g.tick(1)
				if g.loadErr != "" {
					t.Fatalf("ch06_post stopped at %d/%d: %s", g.beatIdx, len(g.beats), g.loadErr)
				}
			}
			if g.camp.NodeID() != "town_ch08" || g.partyMembers[12] != tc.wantJoined {
				t.Fatalf("ch06_post node=%q members=%v wantJoined=%v", g.camp.NodeID(), g.partyMembers, tc.wantJoined)
			}
			joined, ok := g.partyRoster[12]
			if tc.wantJoined {
				if !ok || !joined.HasNativeIdentity || joined.NativeIdentity != 12 ||
					!joined.HasNativeRecordByte5 || joined.NativeRecordByte5 != 0 {
					t.Fatalf("Keli persistent record=%#v", joined)
				}
			} else if ok {
				t.Fatalf("inactive Keli unexpectedly persisted=%#v", joined)
			}
		})
	}
}

func TestChapter8PostJoinsLornaPersistsPartyAndEntersTown9(t *testing.T) {
	g := &Game{}
	if err := g.loadMap("assets/maps/map7"); err != nil {
		t.Fatal(err)
	}
	g.resetBattle("assets/maps/map7/map7_units.json", "assets/scenarios/ch08.json")
	if g.loadErr != "" || g.st == nil || g.sc == nil || !g.sc.RuntimeAppendGroups || len(g.st.Units) != 29 {
		t.Fatalf("chapter8 setup err=%q units=%d runtime_append=%v", g.loadErr, len(g.st.Units), g.sc != nil && g.sc.RuntimeAppendGroups)
	}
	if slot28 := g.st.Units[28]; slot28 == nil || !slot28.HasNativeRecordByte8 || slot28.NativeRecordByte8 != 5 {
		t.Fatalf("chapter8 slot28 must retain raw JOIN5 identity: %#v", slot28)
	}
	order := make([]int, 0, 10)
	g.partyMembers = make(map[int]bool, 10)
	for slot := 0; slot < 10; slot++ {
		unit := g.st.Units[slot]
		if unit == nil || !unit.HasNativeIdentity {
			t.Fatalf("chapter8 party slot%d lacks raw identity: %#v", slot, unit)
		}
		id := unit.NativeIdentity
		order = append(order, id)
		g.partyMembers[id] = true
	}
	g.partyJoinOrder = append([]int(nil), order...)
	if err := g.seedPersistentPartyFromLoadCH(order, g.st.Units[:10]); err != nil {
		t.Fatal(err)
	}
	beats, issues, err := campaign.CompileHandlerBinding(
		assetPath("assets/cutscenes/bindings/ch07_post.json"),
	)
	if err != nil || len(issues) != 0 {
		t.Fatalf("ch07_post compile err=%v issues=%#v", err, issues)
	}
	c := &campaign.Campaign{
		Start: "postbattle_ch08_persist",
		Nodes: map[string]*campaign.Node{
			"postbattle_ch08_persist": {Type: "cutscene", Next: "town_ch09"},
			"town_ch09":               {Type: "town"},
		},
	}
	g.camp = campaign.NewRunner(c)
	g.beats, g.beatIdx, g.storyBG = beats, -1, true
	g.beatAdvance()
	if g.camX != 192 || g.camY != 336 || g.st.Units[28].X != 14 || g.st.Units[28].Y != 16 {
		t.Fatalf("ch07_post layout cam=(%v,%v) slot28=(%d,%d)", g.camX, g.camY, g.st.Units[28].X, g.st.Units[28].Y)
	}
	for frame := 0; frame < 10000 && g.camp.NodeID() != "town_ch09"; frame++ {
		if len(g.dialog) != 0 {
			g.dialog = nil
			g.beatAdvance()
		}
		g.tick(1)
		if g.loadErr != "" {
			t.Fatalf("ch07_post stopped at %d/%d: %s", g.beatIdx, len(g.beats), g.loadErr)
		}
	}
	if g.camp.NodeID() != "town_ch09" || !g.partyMembers[5] || g.handlerChapter != 8 {
		t.Fatalf("ch07_post node=%q members=%v chapter=%d", g.camp.NodeID(), g.partyMembers, g.handlerChapter)
	}
	joined, ok := g.partyRoster[5]
	if !ok || !joined.HasNativeIdentity || joined.NativeIdentity != 5 ||
		!joined.HasNativeRecordByte8 || joined.NativeRecordByte8 != 5 {
		t.Fatalf("洛娜 persistent record=%#v", joined)
	}
	if g.nativeFullDACBlack {
		t.Fatal("town_ch09 must clear the terminal post-battle blackout")
	}
}

func TestChapter10PostRunsExactPaletteAndDirectPatchBeforeTown11(t *testing.T) {
	originalBase := "../../../org_game/炎龍騎士團/FLAME2"
	fdotherPath := filepath.Join(originalBase, "FDOTHER.DAT")
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", fdotherPath)
	order := []int{0, 9, 4, 30, 1, 8, 2, 10, 13, 5}
	g := &Game{partyMembers: make(map[int]bool, len(order)), partyJoinOrder: append([]int(nil), order...)}
	for _, id := range order {
		g.partyMembers[id] = true
	}
	if err := g.loadMap("assets/maps/map9"); err != nil {
		t.Fatal(err)
	}
	g.resetBattle("assets/maps/map9/map9_units.json", "assets/scenarios/ch10.json")
	if g.loadErr != "" || g.st == nil || g.sc == nil || !g.sc.RuntimeAppendGroups || len(g.st.Units) != 52 {
		t.Fatalf("chapter10 setup err=%q units=%d runtime_append=%v", g.loadErr, len(g.st.Units), g.sc != nil && g.sc.RuntimeAppendGroups)
	}
	// Event 32 appends the eight group-1 allies at turn five. This test enters
	// the already-completed battle boundary, so materialize that proven event
	// result directly instead of replaying five unrelated combat rounds.
	g.st.AppendGroup(1)
	if len(g.st.Units) != 60 {
		t.Fatalf("chapter10 post frontier=%d, want 60 without Keli", len(g.st.Units))
	}
	if err := g.seedPersistentPartyFromLoadCH(order, g.st.Units[:len(order)]); err != nil {
		t.Fatal(err)
	}
	emptyX, emptyY, foundEmpty := 0, 0, false
	for y := 0; y < 8 && !foundEmpty; y++ {
		for x := 0; x < 13; x++ {
			if g.st.UnitAt(x, y) == nil {
				emptyX, emptyY, foundEmpty = x, y, true
				break
			}
		}
	}
	if !foundEmpty {
		t.Fatal("chapter10 opening viewport has no empty HUD cursor cell")
	}
	g.curX, g.curY = emptyX, emptyY
	if err := g.st.MaterializeNativeMapViewState(battle.NativeMapViewState{
		CursorX: emptyX, CursorY: emptyY, VisibleCursorX: emptyX, VisibleCursorY: emptyY,
	}); err != nil ||
		!g.st.MaterializeNativeMapHUDState(1, 1, 1) || !g.st.MaterializeNativeMapRangeMode(1) {
		t.Fatalf("chapter10 native view setup err=%v", err)
	}
	if _, ok := g.nativeMapHUDInput(); !ok {
		t.Fatalf("chapter10 HUD input unavailable assets=%v view=%v hud=%v cycle=%v cache=%v cur=(%d,%d) map=%dx%d",
			nativeMapAssetsAvailable(g.nativeMapAssets), g.st.HasNativeMapViewState, g.st.HasNativeMapHUDState,
			g.st.HasNativeMapCycleState, g.st.NativeMapSelectorCache != nil, g.curX, g.curY, g.m.W, g.m.H)
	}
	if err := g.composeNativeMapFrame(); err != nil {
		t.Fatal(err)
	}
	beats, issues, err := campaign.CompileHandlerBinding(assetPath("assets/cutscenes/bindings/ch09_post.json"))
	if err != nil || len(issues) != 0 {
		t.Fatalf("ch09_post compile err=%v issues=%#v", err, issues)
	}
	c := &campaign.Campaign{
		Start: "postbattle_ch10_persist",
		Nodes: map[string]*campaign.Node{
			"postbattle_ch10_persist": {Type: "cutscene", Next: "town_ch11"},
			"town_ch11":               {Type: "town"},
		},
	}
	g.camp = campaign.NewRunner(c)
	g.beats, g.beatIdx, g.storyBG = beats, -1, true
	g.beatAdvance()
	patchObserved, dacRestoredObserved := false, false
	for frame := 0; frame < 10000 && g.camp.NodeID() != "town_ch11"; frame++ {
		if g.nativePaletteRamp != nil {
			g.nativePaletteRamp.drawn = true
		}
		if len(g.dialog) != 0 {
			g.dialog = nil
			g.beatAdvance()
		}
		g.tick(1)
		if g.st != nil && len(g.st.Units) > 52 && g.st.Units[0].X == 14 && g.st.Units[0].Y == 38 &&
			g.st.Units[50].NativeTransient[4] == 0 && g.st.Units[51].NativeTransient[4] == 0 &&
			g.st.Units[52].NativeRecordByte5 == 0 {
			patchObserved = true
		}
		if g.nativeMapAssets != nil && bytes.Equal(g.nativeMapDAC, g.nativeMapAssets.PaletteDAC) && patchObserved {
			dacRestoredObserved = true
		}
		if g.loadErr != "" {
			t.Fatalf("ch09_post stopped at %d/%d: %s", g.beatIdx, len(g.beats), g.loadErr)
		}
	}
	if g.camp.NodeID() != "town_ch11" || !g.partyMembers[11] || !g.partyMembers[6] || g.handlerChapter != 10 {
		t.Fatalf("ch09_post node=%q members=%v chapter=%d", g.camp.NodeID(), g.partyMembers, g.handlerChapter)
	}
	if !patchObserved || !dacRestoredObserved {
		t.Fatalf("ch09_post patch/DAC observation patch=%v restored=%v", patchObserved, dacRestoredObserved)
	}
	for _, id := range []int{11, 6} {
		joined, ok := g.partyRoster[id]
		if !ok || !joined.HasNativeIdentity || joined.NativeIdentity != id || !joined.HasNativeRecordByte8 || int(joined.NativeRecordByte8) != id {
			t.Fatalf("joined %d persistent record=%#v", id, joined)
		}
	}
}

func TestChapter10PostRuntimeFrontiersTrackConditionalKailey(t *testing.T) {
	tests := []struct {
		name  string
		order []int
		want  int
	}{
		{name: "without_Kailey", order: []int{0, 9, 4, 30, 1, 8, 2, 10, 13, 5}, want: 60},
		{name: "with_Kailey", order: []int{0, 9, 4, 30, 1, 8, 2, 10, 13, 12, 5}, want: 61},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			g := &Game{
				partyMembers:   make(map[int]bool, len(test.order)),
				partyJoinOrder: append([]int(nil), test.order...),
			}
			for _, id := range test.order {
				g.partyMembers[id] = true
			}
			if err := g.loadMap("assets/maps/map9"); err != nil {
				t.Fatal(err)
			}
			g.resetBattle("assets/maps/map9/map9_units.json", "assets/scenarios/ch10.json")
			if g.loadErr != "" || g.st == nil || g.sc == nil || !g.sc.RuntimeAppendGroups {
				t.Fatalf("chapter10 setup err=%q runtime_append=%v", g.loadErr, g.sc != nil && g.sc.RuntimeAppendGroups)
			}
			g.st.AppendGroup(1)
			if len(g.st.Units) != test.want {
				t.Fatalf("chapter10 post frontier=%d, want %d", len(g.st.Units), test.want)
			}
		})
	}
}
