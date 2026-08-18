package main

import "testing"

import "github.com/wicanr2/fd2_re/remake/internal/campaign"

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
