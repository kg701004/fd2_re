package main

import (
	"strings"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestUnboundPostbattleCutsceneFailsClosed(t *testing.T) {
	c := &campaign.Campaign{
		Start: "postbattle_ch04_persist",
		Nodes: map[string]*campaign.Node{
			"postbattle_ch04_persist": {Type: "cutscene", Next: "town_ch05"},
			"town_ch05":               {Type: "town"},
		},
	}
	g := &Game{camp: campaign.NewRunner(c)}
	g.enterNode()
	if got := g.camp.NodeID(); got != "postbattle_ch04_persist" {
		t.Fatalf("unbound postbattle advanced to %q", got)
	}
	if !strings.Contains(g.loadErr, "no active handler binding") || g.msg == "" {
		t.Fatalf("missing fail-closed diagnostics: loadErr=%q msg=%q", g.loadErr, g.msg)
	}
}
