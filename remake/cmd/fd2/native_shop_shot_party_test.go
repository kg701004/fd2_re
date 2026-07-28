package main

import (
	"image/color"
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func TestParseNativeShopEquipmentRecipientShotState(t *testing.T) {
	for _, tc := range []struct {
		spec                                string
		good, selection, start, cycle, gold int
		ok                                  bool
	}{
		{spec: "0,0,0,0,1000", gold: 1000, ok: true},
		{spec: "3,2,1,2,99999999", good: 3, selection: 2, start: 1, cycle: 2, gold: 99999999, ok: true},
		{spec: "-1,0,0,0,1000"},
		{spec: "0,-1,0,0,1000"},
		{spec: "0,0,-1,0,1000"},
		{spec: "0,0,0,-1,1000"},
		{spec: "0,0,0,3,1000"},
		{spec: "0,0,0,0,-1"},
		{spec: "0,0,0,0,100000000"},
		{spec: "0,0,0,0"},
		{spec: "0,0,0,0,1,2"},
		{spec: "x,0,0,0,1"},
	} {
		good, selection, start, cycle, gold, ok :=
			parseNativeShopEquipmentRecipientShotState(tc.spec)
		if good != tc.good || selection != tc.selection ||
			start != tc.start || cycle != tc.cycle ||
			gold != tc.gold || ok != tc.ok {
			t.Fatalf(
				"parseNativeShopEquipmentRecipientShotState(%q)=(%d,%d,%d,%d,%d,%v), want (%d,%d,%d,%d,%d,%v)",
				tc.spec, good, selection, start, cycle, gold, ok,
				tc.good, tc.selection, tc.start, tc.cycle, tc.gold, tc.ok,
			)
		}
	}
}

func TestNativeShopEquipmentRecipientShotUsesBindingPartyProjection(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2"
	fdotherPath := filepath.Join(base, "FDOTHER.DAT")
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided original resources are absent")
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", fdotherPath)
	t.Setenv("FD2_ORIGINAL_FDTXT", filepath.Join(base, "FDTXT.DAT"))
	t.Setenv("FD2_ORIGINAL_DATO", filepath.Join(base, "DATO.DAT"))

	shared, err := loadNativeClassUIAssets()
	if err != nil {
		t.Fatal(err)
	}
	shop, err := loadNativeShopUIAssets(shared)
	if err != nil {
		t.Fatal(err)
	}
	c, err := campaign.Load(assetPath("assets/scenarios/campaign_full.json"))
	if err != nil {
		t.Fatal(err)
	}
	runner := campaign.NewRunner(c)
	runner.Cur = "shop_ch02_weapon"
	types, equip, err := campaign.LoadShopEligibility(
		assetPath("assets/data/item.json"),
		assetPath("assets/data/class_equip_types.json"),
	)
	if err != nil {
		t.Fatal(err)
	}
	stats, err := campaign.LoadItemStats(assetPath("assets/data/item.json"))
	if err != nil {
		t.Fatal(err)
	}
	g := &Game{
		shotPath:      "recipient.png",
		camp:          runner,
		nativeClassUI: shared,
		nativeShopUI:  shop,
		nativeUIPalette: append(
			color.Palette(nil), shared.palette...,
		),
		shopItemTypes:  types,
		shopEquipTypes: equip,
		shopItemStats:  stats,
	}
	if err := g.materializeShotPartyFromBinding(
		"assets/cutscenes/bindings/ch00_pre.json",
	); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(g.partyJoinOrder, []int{0, 9, 4, 30}) {
		t.Fatalf("binding party order=%v", g.partyJoinOrder)
	}
	if !g.setupNativeShop() {
		t.Fatal("ch02 weapon shop did not admit native owner")
	}
	g.nativeShopUIJob = nil
	if !g.setNativeShopEquipmentRecipientShotState(0, 0, 0, 1, 1000) {
		t.Fatal("equipment recipient state rejected verified binding party")
	}
	if g.nativeShopRecipientCycle != 1 {
		t.Fatalf("recipient cycle=%d", g.nativeShopRecipientCycle)
	}
	if !reflect.DeepEqual(g.shopRecipients, []int{0, 9, 4}) {
		t.Fatalf("equipment recipients=%v, want original visible order", g.shopRecipients)
	}
	wantStats := map[int]struct {
		current, candidate [4]int
	}{
		0: {current: [4]int{16, 12, 97, 2}, candidate: [4]int{16, 6, 97, 2}},
		9: {current: [4]int{11, 7, 86, 1}, candidate: [4]int{11, 4, 86, 1}},
		4: {current: [4]int{26, 6, 92, 2}, candidate: [4]int{26, 6, 92, 2}},
	}
	for _, id := range g.shopRecipients {
		unit := g.partyRoster[id]
		record, err := campaign.NativeShopEquipmentRecordForUnit(&unit)
		if err != nil {
			t.Fatal(err)
		}
		current, err := campaign.NativeShopEquipmentCurrentStats(record)
		if err != nil {
			t.Fatal(err)
		}
		candidate, err := campaign.NativeShopEquipmentCandidateStats(
			record, 0x80, g.nativeShopUI.effectRows,
		)
		if err != nil {
			t.Fatal(err)
		}
		if current != wantStats[id].current ||
			candidate != wantStats[id].candidate {
			t.Fatalf(
				"recipient %d stats current=%v candidate=%v want=%v/%v",
				id, current, candidate,
				wantStats[id].current, wantStats[id].candidate,
			)
		}
	}
	frame, ok := g.composeNativeShopEquipmentRecipient()
	if !ok || len(frame) != 320*200 {
		t.Fatal("equipment recipient did not pass final compositor admission")
	}

	oldMode, oldSelection, oldStart, oldGold :=
		g.nativeShopMode, g.shopRecipientSel, g.nativeShopRecipientStart, g.gold
	if g.setNativeShopEquipmentRecipientShotState(0, 3, 0, 0, 1000) ||
		g.nativeShopMode != oldMode ||
		g.shopRecipientSel != oldSelection ||
		g.nativeShopRecipientStart != oldStart || g.gold != oldGold {
		t.Fatal("out-of-range recipient state did not fail atomically")
	}
}

func TestShotPartyBindingRequiresScreenshotAndCompletePartyLoadCH(t *testing.T) {
	g := &Game{}
	if err := g.materializeShotPartyFromBinding(
		"assets/cutscenes/bindings/ch00_pre.json",
	); err == nil {
		t.Fatal("party binding accepted non-screenshot runtime")
	}
	g.shotPath = "shot.png"
	if err := g.materializeShotPartyFromBinding(
		"assets/cutscenes/bindings/ch00_post.json",
	); err == nil {
		t.Fatal("party binding accepted handler without complete party LOADCH")
	}
}
