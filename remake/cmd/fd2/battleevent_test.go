package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
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
