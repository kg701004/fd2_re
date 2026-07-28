package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestNativeShopProductionOwnerDrawsOriginalMenuAndPurchaseList(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2"
	fdotherPath := filepath.Join(base, "FDOTHER.DAT")
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided original resources are absent")
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", fdotherPath)
	t.Setenv("FD2_ORIGINAL_FDTXT", filepath.Join(base, "FDTXT.DAT"))

	shared, err := loadNativeClassUIAssets()
	if err != nil {
		t.Fatal(err)
	}
	shop, err := loadNativeShopUIAssets(shared)
	if err != nil {
		t.Fatal(err)
	}
	c := &campaign.Campaign{
		Start: "shop",
		Nodes: map[string]*campaign.Node{
			"shop": {
				Type: "shop", NativeHubVariant: 1,
				Goods: []campaign.Good{
					{ID: 0, Name: "item0", Price: 100},
					{ID: 1, Name: "item1", Price: 200},
				},
			},
		},
	}
	g := &Game{
		camp:          campaign.NewRunner(c),
		nativeClassUI: shared,
		nativeShopUI:  shop,
		gold:          1234,
	}
	if !g.setupNativeShop() || g.nativeShopMode != "menu" ||
		g.nativeShopUIJob == nil || len(g.nativeShopUIJob.frames) != 4 {
		t.Fatal("native shop did not claim the original node with four-frame service opening")
	}
	screen := ebiten.NewImage(640, 400)
	g.nativeShopUIJob = nil
	if !g.drawNativeShop(screen) {
		t.Fatal("native shop service menu unexpectedly fell back")
	}
	g.nativeShopMode = "purchase"
	if !g.drawNativeShop(screen) {
		t.Fatal("native shop purchase list unexpectedly fell back")
	}
	if !g.beginNativeShopPurchaseOpening() ||
		len(g.nativeShopUIJob.frames) != 6 {
		t.Fatal("native shop purchase list did not use the six-frame original lifecycle")
	}
	g.nativeShopUIJob = nil
	if !g.beginNativeShopPurchaseClosing(nil) ||
		len(g.nativeShopUIJob.frames) != 5 ||
		len(g.nativeShopUIJob.restore) != 320*200 {
		t.Fatal("native shop purchase list did not use five close frames and stable restore")
	}
}

func TestNativeShopProductionOwnerFailsClosedForCustomVariant(t *testing.T) {
	g := &Game{
		camp: campaign.NewRunner(&campaign.Campaign{
			Start: "shop",
			Nodes: map[string]*campaign.Node{
				"shop": {Type: "shop", NativeHubVariant: 0},
			},
		}),
	}
	if g.setupNativeShop() || g.nativeShopMode != "" {
		t.Fatal("custom shop node was incorrectly claimed by original shop owner")
	}
}
