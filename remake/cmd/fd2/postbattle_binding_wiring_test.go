package main

import "testing"

import (
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

// TestPostbattleCh16UsesPromotedCh15Binding covers the 2026-08-17 fix for
// one of the 7 chapters whose postbattle_chNN_persist node had no
// handler_binding at all (see 58-remake-live-verification-log.md's
// postbattle_chNN_persist section): reaching postbattle_ch16_persist used to
// fail-closed-stall on "戰後 handler 尚未接線,流程已停止" because
// assets/cutscenes/bindings/ch15_post.json never existed -- only a
// ch15_post_candidate.json with equivalent data sat unpromoted. This
// promotes that candidate's already-correct dialogue/layout/act data (its
// handler_script, dialogue_contexts, layout override, and act override all
// reused verbatim) onto the standard chNN_post.json name so the existing
// N-1 handler_binding convention (postbattle_ch(N+1) uses chN_post.json,
// see ch04..ch29's existing bindings) picks it up.
func TestPostbattleCh16UsesPromotedCh15Binding(t *testing.T) {
	c, err := campaign.Load(assetPath("assets/scenarios/campaign_full.json"))
	if err != nil {
		t.Fatal(err)
	}
	n := c.Nodes["postbattle_ch16_persist"]
	if n == nil {
		t.Fatal("postbattle_ch16_persist node not found")
	}
	if n.HandlerBinding == "" {
		t.Fatal("postbattle_ch16_persist still has no handler_binding")
	}
	beats, issues, err := campaign.CompileHandlerBinding(assetPath(n.HandlerBinding))
	if err != nil {
		t.Fatalf("compile error: %v", err)
	}
	if len(issues) != 0 {
		t.Fatalf("binding has %d unresolved issue(s): %#v", len(issues), issues)
	}
	if len(beats) == 0 {
		t.Fatal("binding compiled to zero beats")
	}
}

// TestPostbattleCh18UsesFreshCh17Binding covers ch17 (postbattle_ch18_persist,
// needing ch17_post.json), the second of the 7 originally-unbound chapters.
// Unlike ch16, no pre-existing candidate data was sitting unused for this
// one -- the layout_units unit-position table (17 slots + one special-cased
// extra) was recovered 2026-08-17 by force-disassembling the handler's own
// call site (0x23d39) via a headless Ghidra probe against the FD2Analysis3
// project (see reference_fd2_live_ghidra_headless_probe memory): the call
// site loads three 17-byte data tables (X array, Y array, pose array) from
// fixed addresses 0x521c3/0x521d4/0x521e5 into local stack buffers before
// calling the shared layout writer (0x233c6, the same callee ch15/ch16's
// layout_units already use) -- reading those raw bytes and the callee's own
// per-index write loop gave the exact per-slot x/y/pose plus the one
// special-cased extra slot (17) and camera position, all verbatim in
// ch17_post.json's "layout" override, not guessed.
func TestPostbattleCh18UsesFreshCh17Binding(t *testing.T) {
	c, err := campaign.Load(assetPath("assets/scenarios/campaign_full.json"))
	if err != nil {
		t.Fatal(err)
	}
	n := c.Nodes["postbattle_ch18_persist"]
	if n == nil {
		t.Fatal("postbattle_ch18_persist node not found")
	}
	if n.HandlerBinding == "" {
		t.Fatal("postbattle_ch18_persist still has no handler_binding")
	}
	beats, issues, err := campaign.CompileHandlerBinding(assetPath(n.HandlerBinding))
	if err != nil {
		t.Fatalf("compile error: %v", err)
	}
	if len(issues) != 0 {
		t.Fatalf("binding has %d unresolved issue(s): %#v", len(issues), issues)
	}
	if len(beats) == 0 {
		t.Fatal("binding compiled to zero beats")
	}
}

// TestPostbattleCh24UsesPromotedCh23Binding covers ch24 (postbattle_ch24_persist,
// needing ch23_post.json), the 3rd of the originally-unbound chapters promoted
// as part of M5 Phase 1 (2026-08-31). Its only 3 CompileHandlerBinding issues
// were both native_target 0x24d22 (a result-screen DAC-tier setter, proven
// dead in this call context by doc58's 續二十八 exhaustive static decompile,
// commit 7093ca16) and one native_target 0x11d40 (a 60-step whole-DAC
// cross-fade, approximated with the already-proven binary palette_update
// full-white primitive since the smooth indexed ramp renderer only serves
// loadch-entered story-viewport scenes, not this loadch-less battle
// continuation). See handler_compile.go's "unknown" case for both lowerings.
func TestPostbattleCh24UsesPromotedCh23Binding(t *testing.T) {
	c, err := campaign.Load(assetPath("assets/scenarios/campaign_full.json"))
	if err != nil {
		t.Fatal(err)
	}
	n := c.Nodes["postbattle_ch24_persist"]
	if n == nil {
		t.Fatal("postbattle_ch24_persist node not found")
	}
	if n.HandlerBinding == "" {
		t.Fatal("postbattle_ch24_persist still has no handler_binding")
	}
	beats, issues, err := campaign.CompileHandlerBinding(assetPath(n.HandlerBinding))
	if err != nil {
		t.Fatalf("compile error: %v", err)
	}
	if len(issues) != 0 {
		t.Fatalf("binding has %d unresolved issue(s): %#v", len(issues), issues)
	}
	if len(beats) == 0 {
		t.Fatal("binding compiled to zero beats")
	}
}

// TestPostbattleCh24BindingRendersRealDialogueAndCrossfade drives the real
// compiled ch23_post.json beats through the BeatRunner (not synthetic
// beats), popping each dialog line and ticking delay/redraw beats exactly as
// the production cutscene input handler would, to confirm the whole sequence
// -- including the two new native_result_tier_set/palette_update lowerings
// -- actually executes to completion without g.loadErr, not merely that the
// campaign graph resolves. Complements the real-window FD2_SHOT screenshot
// spot check (M5 Phase 1 worklist entry) which independently confirmed the
// first dialogue line renders on screen with real Traditional Chinese text.
func TestPostbattleCh24BindingRendersRealDialogueAndCrossfade(t *testing.T) {
	beats, issues, err := campaign.CompileHandlerBinding(assetPath("assets/cutscenes/bindings/ch23_post.json"))
	if err != nil || len(issues) != 0 {
		t.Fatalf("compile err=%v issues=%#v", err, issues)
	}
	g := newBeatTestGame(t, beats)
	g.partyMembers = map[int]bool{0: true}
	g.st = &battle.State{Units: []*battle.Unit{
		{Camp: battle.Own, Fig: 0, Name: "test", Lv: 1, HP: 10, MaxHP: 10, OnField: true},
	}}
	g.beatAdvance()
	sawWhiteFlash := false
	for iterations := 0; iterations < 300 && g.loadErr == ""; iterations++ {
		if g.nativeFullDACWhite {
			sawWhiteFlash = true
		}
		if len(g.dialog) > 0 {
			g.dialog = g.dialog[:len(g.dialog)-1]
			if len(g.dialog) == 0 {
				g.beatAdvance()
			}
			continue
		}
		if g.beatDelay > 0 {
			g.tick(1)
			continue
		}
		break // sequence finished (advanceStoryNode fired) or genuinely stuck
	}
	if g.loadErr != "" {
		t.Fatalf("beat sequence errored: %s", g.loadErr)
	}
	if g.handlerChapter != 24 {
		t.Fatalf("handlerChapter = %d, want 24 (set_chapter beat did not run)", g.handlerChapter)
	}
	if !sawWhiteFlash {
		t.Fatal("expected the 0x11d40 cross-fade approximation to trigger nativeFullDACWhite")
	}
	if g.fade == nil {
		t.Fatal("beat sequence completing should hand off to advanceStoryNode's transition")
	}
}
