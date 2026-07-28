package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
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
	g.nativeShopUIJob = nil
	g.nativeShopMode = "confirm"
	g.nativeShopConfirmSel = 0
	if !g.drawNativeShop(screen) {
		t.Fatal("native shop purchase confirmation unexpectedly fell back")
	}
	if !g.beginNativeShopConfirmationOpening() ||
		len(g.nativeShopUIJob.frames) != 4 {
		t.Fatal("native shop confirmation did not use four original opening frames")
	}
	g.nativeShopUIJob = nil
	if !g.beginNativeShopConfirmationChoiceClosing(nil) ||
		len(g.nativeShopUIJob.frames) != 4 {
		t.Fatal("native shop confirmation did not use four original closing frames")
	}
	postChoiceClose := append(
		[]byte(nil),
		g.nativeShopUIJob.frames[len(g.nativeShopUIJob.frames)-1]...,
	)
	g.nativeShopUIJob = nil
	g.nativeShopMode = "insufficient"
	insufficient, ok := g.composeNativeShopInsufficientGold()
	if !ok || string(insufficient) == string(postChoiceClose) {
		t.Fatal("native shop insufficient-gold feedback did not append after choice close")
	}
	if !g.beginNativeShopDialogueClosing(insufficient, nil) ||
		len(g.nativeShopUIJob.frames) != 5 ||
		len(g.nativeShopUIJob.restore) != 320*200 {
		t.Fatal("native shop insufficient-gold feedback did not use five dialogue close frames")
	}
	unit := battle.Unit{
		BattleFig: 0, NativeIdentity: 0, HasNativeIdentity: true,
		MapSelectorKey: 0, HasMapSelectorKey: true,
		NativeRecordByte6: 1, HasNativeRecordByte6: true,
		NativeRecordRace: 1, HasNativeRecordRace: true,
		NativeRecordClass: 1, HasNativeRecordClass: true,
		Lv: 8, MV: 5, Exp: 10, DX: 17,
		HP: 30, MaxHP: 35, MP: 5, MaxMP: 9,
		AP: 41, DP: 32, HIT: 70, EV: 22,
		InventorySlots:       []int{0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
		BaseAP:               29, BaseDP: 25, EquipmentBaseSet: true,
	}
	g.nativeShopUIJob = nil
	g.partyJoinOrder = []int{0}
	g.partyRoster = map[int]battle.Unit{0: unit}
	g.shopItemTypes = map[int]int{0: 0x20}
	g.shopEquipTypes = map[int][]int{1: []int{0, 1, 2, 3, 4, 5}}
	if !g.setupNativeShopRecipients() ||
		g.nativeShopMode != "recipient_consumable" ||
		!g.drawNativeShop(screen) {
		t.Fatal("native consumable recipient production owner unexpectedly fell back")
	}
	if !g.beginNativeShopRecipientOpening() ||
		len(g.nativeShopUIJob.frames) != 6 {
		t.Fatal("native consumable recipient did not use six opening frames")
	}
	g.nativeShopUIJob = nil
	if !g.beginNativeShopRecipientClosing(nil) ||
		len(g.nativeShopUIJob.frames) != 5 ||
		len(g.nativeShopUIJob.restore) != 320*200 {
		t.Fatal("native consumable recipient did not use five close frames")
	}
	g.nativeShopUIJob = nil
	g.shopItemTypes[0] = 0
	if !g.setupNativeShopRecipients() ||
		g.nativeShopMode != "recipient_equipment" ||
		!g.drawNativeShop(screen) {
		t.Fatal("native equipment recipient production owner unexpectedly fell back")
	}
	for i := range unit.NativeInventoryFlags {
		unit.NativeInventoryFlags[i] = 0
		unit.InventorySlots[i] = i
	}
	g.partyRoster[0] = unit
	g.nativeShopMode = "recipient_full"
	if !nativeShopInventoryFull(unit) || !g.drawNativeShop(screen) {
		t.Fatal("native recipient-full production feedback unexpectedly fell back")
	}
	if !g.beginNativeShopRecipientFullOpening() ||
		len(g.nativeShopUIJob.frames) != 6 {
		t.Fatal("native recipient-full feedback did not use six opening frames")
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
