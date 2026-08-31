package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestDefaultChapterStoryScriptOnlyMatchesGenericStoryNodes(t *testing.T) {
	for _, tc := range []struct {
		id, want string
	}{
		{"story_ch04", "assets/story/ch04.json"},
		{"story_ch30", "assets/story/ch30.json"},
		{"story_ch01_pre", ""},
		{"story_ch21_post_sky_key_intro", ""},
		{"story_ch00_handler", ""},
	} {
		if got := defaultChapterStoryScript(tc.id); got != tc.want {
			t.Fatalf("defaultChapterStoryScript(%q)=%q, want %q", tc.id, got, tc.want)
		}
	}
}

// TestStoryCh23Ch29Ch30ResolveViaDefaultFallback locks in a finding from the
// M5 planning audit (2026-08-31): campaign_full.json's story_ch23/29/30 nodes
// carry no explicit "script" field, which an earlier planning pass flagged as
// a possible content gap. It isn't one -- enterNode's story/cutscene branch
// (main.go, "script == "" && n.Type == "story"") already falls back to
// defaultChapterStoryScript for exactly this shape, and assets/story/ch23,
// ch29, ch30.json all carry real, non-trivial authored dialogue. This test
// exercises both halves end to end so a future edit that breaks either the
// campaign node's empty-script assumption or the story file's content can't
// silently regress.
func TestStoryCh23Ch29Ch30ResolveViaDefaultFallback(t *testing.T) {
	c, err := campaign.Load(assetPath("assets/scenarios/campaign_full.json"))
	if err != nil {
		t.Fatal(err)
	}
	for _, chapter := range []string{"23", "29", "30"} {
		nodeID := "story_ch" + chapter
		n := c.Nodes[nodeID]
		if n == nil {
			t.Fatalf("%s missing from campaign_full.json", nodeID)
		}
		if n.Type != "story" {
			t.Fatalf("%s type=%q, want story", nodeID, n.Type)
		}
		if n.Script != "" {
			t.Fatalf("%s already has an explicit script=%q; this test's fallback-path premise no longer holds, update it instead of deleting it", nodeID, n.Script)
		}
		script := defaultChapterStoryScript(nodeID)
		if script == "" {
			t.Fatalf("defaultChapterStoryScript(%q) returned empty", nodeID)
		}
		lines := loadStoryScript(script, n.Scene)
		if len(lines) == 0 {
			t.Fatalf("%s: %s resolved but loadStoryScript returned zero lines", nodeID, script)
		}
	}
}
