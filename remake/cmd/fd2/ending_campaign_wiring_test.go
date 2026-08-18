package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

// TestEnterNodeAttemptsNativeEndingOnlyForTrueEndingNode covers the
// 2026-08-17 fix for the "player reaches the true ending and is stuck on a
// screen that admits it's a generator placeholder, with no way out" bug
// (see 58-remake-live-verification-log.md's #109 section). enterNode's
// "ending" case must only attempt newNativeEndingPreview() for the node ID
// "ending" (the true post-ch30 victory node) -- a bad-ending node sharing the
// same Type must keep the plain text panel, since there is no disassembly
// evidence the recovered 0x2bce5 timeline applies to it.
func TestEnterNodeAttemptsNativeEndingOnlyForTrueEndingNode(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2"
	for _, name := range []string{"FDOTHER.DAT", "FDTXT.DAT", "ANI.DAT"} {
		if _, err := os.Stat(filepath.Join(base, name)); os.IsNotExist(err) {
			t.Skip("player-provided ending resources are unavailable")
		} else if err != nil {
			t.Fatal(err)
		}
	}
	t.Setenv("FD2_FDOTHER", filepath.Join(base, "FDOTHER.DAT"))
	t.Setenv("FD2_FDTXT", filepath.Join(base, "FDTXT.DAT"))
	t.Setenv("FD2_ANI", filepath.Join(base, "ANI.DAT"))

	c := &campaign.Campaign{Start: "ending", Nodes: map[string]*campaign.Node{
		"ending": {Type: "ending", Text: "real ending text"},
	}}
	g := &Game{camp: campaign.NewRunner(c)}
	g.enterNode()
	if g.nativeEnding == nil {
		t.Fatal("true ending node must attempt the native 0x2bce5 preview when player-provided assets are available")
	}

	c2 := &campaign.Campaign{Start: "ending_ch27_no_sky_key", Nodes: map[string]*campaign.Node{
		"ending_ch27_no_sky_key": {Type: "ending", Text: "bad ending text"},
	}}
	g2 := &Game{camp: campaign.NewRunner(c2)}
	g2.enterNode()
	if g2.nativeEnding != nil {
		t.Fatal("bad-ending node must not attempt the native preview -- no disassembly evidence it applies there")
	}
}

// TestEnterNodeEndingGracefulWithoutNativeAssets covers the common case
// (player-provided FDOTHER.DAT/ANI.DAT/FDTXT.DAT never bundled): reaching
// the ending node must not error or panic when newNativeEndingPreview()
// fails, it must fall back to the plain text panel (g.nativeEnding stays
// nil, g.loadErr stays empty -- draw()'s "ending" node-type case then
// renders g.camp.Node().Text, and campInput's "ending" case now provides a
// real Enter/Escape exit instead of absorbing every keypress forever).
func TestEnterNodeEndingGracefulWithoutNativeAssets(t *testing.T) {
	t.Setenv("FD2_FDOTHER", filepath.Join(t.TempDir(), "missing.DAT"))
	t.Setenv("FD2_ANI", filepath.Join(t.TempDir(), "missing.DAT"))
	t.Setenv("FD2_FDTXT", filepath.Join(t.TempDir(), "missing.DAT"))

	c := &campaign.Campaign{Start: "ending", Nodes: map[string]*campaign.Node{
		"ending": {Type: "ending", Text: "real ending text"},
	}}
	g := &Game{camp: campaign.NewRunner(c)}
	g.enterNode()
	if g.nativeEnding != nil {
		t.Fatal("missing player-provided assets must not fabricate a native preview")
	}
	if g.loadErr != "" {
		t.Fatalf("missing player-provided ending assets must not surface as a load error, got %q", g.loadErr)
	}
	if g.camp.Node().Text != "real ending text" {
		t.Fatalf("plain-text ending fallback must still show the node's real text, got %q", g.camp.Node().Text)
	}
}

// TestCampInputEndingRequestsQuitOnEnterOrEscape covers the "player is
// stuck forever" half of the same bug: campInput's "ending" case used to
// unconditionally `return true` with no way to leave. It now sets
// g.wantQuit so the Update() call site can return ebiten.Termination. This
// only exercises the flag directly (ebiten's key-press polling requires a
// live RunGame event loop that plain `go test` never drives, matching this
// project's existing convention of verifying key-driven UI via the
// screenshot harness, not inpututil simulation in unit tests) -- so this
// test's job is to prove wantQuit starts false and is a real, read field on
// Game, not to simulate the keypress itself.
func TestCampInputEndingRequestsQuitOnEnterOrEscape(t *testing.T) {
	c := &campaign.Campaign{Start: "ending", Nodes: map[string]*campaign.Node{
		"ending": {Type: "ending", Text: "bad ending, plain text only"},
	}}
	g := &Game{camp: campaign.NewRunner(c)}
	if g.wantQuit {
		t.Fatal("wantQuit must default to false")
	}
	if g.campInput() != true {
		t.Fatal("campInput must still intercept input on the ending node even without a keypress this tick")
	}
}

// TestCampaignFullJSONEndingTextIsNotAGeneratorPlaceholder is a content
// regression guard for the exact bug 58-remake-live-verification-log.md's
// #109 section screenshotted: campaign_full.json's "ending" node text used
// to literally read as an internal generator note ("v1:節點骨架完整...待下一
// 輪補完"), which the game rendered verbatim to the player. It's since been
// replaced with real chapter-30 narration (see assets/story/ch30.json's
// "location" field) -- this only guards against that specific leak
// reappearing, not the full text's fidelity.
func TestCampaignFullJSONEndingTextIsNotAGeneratorPlaceholder(t *testing.T) {
	data, err := os.ReadFile(assetPath("assets/scenarios/campaign_full.json"))
	if err != nil {
		t.Fatal(err)
	}
	text := string(data)
	for _, leak := range []string{"自動生成", "待下一輪補完", "節點骨架完整"} {
		if strings.Contains(text, leak) {
			t.Fatalf("campaign_full.json still contains generator-note leak %q", leak)
		}
	}
}
