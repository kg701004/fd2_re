package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestNativeTownProductionOwnerUsesEditableVariantAndHiddenSelection(t *testing.T) {
	base := filepath.Join("..", "..", "..", "org_game", "炎龍騎士團", "FLAME2")
	if _, err := os.Stat(filepath.Join(base, "FDOTHER.DAT")); err != nil {
		t.Skip("player-provided original resources are absent")
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", filepath.Join(base, "FDOTHER.DAT"))
	t.Setenv("FD2_ORIGINAL_FDTXT", filepath.Join(base, "FDTXT.DAT"))
	t.Setenv("FD2_ORIGINAL_DATO", filepath.Join(base, "DATO.DAT"))
	shared, err := loadNativeClassUIAssets()
	if err != nil {
		t.Fatal(err)
	}
	town, err := loadNativeTownUIAssets()
	if err != nil {
		t.Fatal(err)
	}
	variant := 2
	c := &campaign.Campaign{
		Start: "town",
		Nodes: map[string]*campaign.Node{
			"town": {
				Type:              "town",
				NativeTownVariant: &variant,
				NativeSecretGate: &campaign.NativeTownSecretGate{
					Selection: 1, ScanCode: 0x5f, To: "secret",
				},
			},
			"secret": {Type: "shop", NativeHubVariant: 5},
		},
	}
	g := &Game{
		camp:          campaign.NewRunner(c),
		campSel:       1,
		nativeClassUI: shared,
		nativeTownUI:  town,
	}
	visible, ok := g.composeNativeTownFrame()
	if !ok || len(visible) != 320*200 {
		t.Fatalf("visible native town frame=%d ok=%v", len(visible), ok)
	}
	if !g.camp.MatchNativeTownSecret(g.campSel, 0x5f) ||
		g.camp.NodeID() != "town" {
		t.Fatal("native secret chord did not remain in the town owner")
	}
	g.campSel = 5
	hidden, ok := g.composeNativeTownFrame()
	if !ok || bytes.Equal(visible, hidden) {
		t.Fatal("hidden selection did not redraw the native town frame")
	}
	if !g.camp.ConfirmNativeTownSecret(g.campSel) ||
		g.camp.NodeID() != "secret" {
		t.Fatal("confirmed hidden selection did not dispatch variant 5")
	}
}

func TestNativeTownPulseUsesFourTickSignedDelta(t *testing.T) {
	g := &Game{}
	for _, tc := range []struct {
		tick int
		want int
	}{
		{0x7ffe, 0},
		{0x7fff, 0},
		{-0x7ffe, 1},
		{-0x7ffa, 2},
		{-0x7fF6, 3},
		{-0x7fF2, 0},
	} {
		g.stepNativeTownUIPulseTick(tc.tick)
		if g.nativeTownUIPulse != tc.want {
			t.Fatalf(
				"tick %#x pulse=%d want %d",
				tc.tick, g.nativeTownUIPulse, tc.want,
			)
		}
	}
}

func TestNativeTownSelectionUsesOriginalLeftRightWrap(t *testing.T) {
	for _, tc := range []struct {
		selection int
		delta     int
		want      int
	}{
		{0, -1, 4},
		{4, 1, 0},
		{2, -1, 1},
		{2, 1, 3},
		{5, -1, 4},
		{5, 1, 0},
	} {
		got, ok := nativeTownMoveSelection(tc.selection, tc.delta)
		if !ok || got != tc.want {
			t.Fatalf(
				"selection=%d delta=%d got=%d ok=%v want=%d",
				tc.selection, tc.delta, got, ok, tc.want,
			)
		}
	}
	for _, invalid := range [][2]int{{-1, 1}, {6, -1}, {0, 0}} {
		if _, ok := nativeTownMoveSelection(invalid[0], invalid[1]); ok {
			t.Fatalf("invalid move %#v was accepted", invalid)
		}
	}
}
