package main

import (
	"os"
	"testing"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func nativeItemPanelTestUnit() *battle.Unit {
	return &battle.Unit{
		BattleFig: 0, NativeIdentity: 0, HasNativeIdentity: true,
		NativeRecordByte6: 1, HasNativeRecordByte6: true,
		NativeRecordRace: 1, HasNativeRecordRace: true,
		NativeRecordClass: 1, HasNativeRecordClass: true,
		Lv: 12, MV: 5, Exp: 34, DX: 56,
		HP: 80, MaxHP: 100, MP: 20, MaxMP: 40,
		AP: 123, DP: 98, HIT: 76, EV: 54,
		InventorySlots:       []int{0, 0xff, 79, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0x40, 0x80, 0, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
}

func TestNativeItemRawSlotsCompactsDisplayWithoutMovingRecords(t *testing.T) {
	unit := nativeItemPanelTestUnit()
	got := nativeItemRawSlots(unit)
	if len(got) != 2 || got[0] != 0 || got[1] != 2 {
		t.Fatalf("raw slots=%v", got)
	}
}

func TestPrepareNativeItemPanelAndTwelveFramePlayerWithOriginalAssets(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2/"
	for _, name := range []string{"FDOTHER.DAT", "FDTXT.DAT", "DATO.DAT"} {
		if _, err := os.Stat(base + name); err != nil {
			t.Skip("player-provided original archives are absent")
		}
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", base+"FDOTHER.DAT")
	t.Setenv("FD2_ORIGINAL_FDTXT", base+"FDTXT.DAT")
	t.Setenv("FD2_ORIGINAL_DATO", base+"DATO.DAT")
	g := &Game{sel: nativeItemPanelTestUnit(), itemOpen: true}
	g.nativeUIPalette = loadNativeUIPalette()
	if !g.prepareNativeItemPanel(g.sel) || g.nativeItemPanel == nil {
		t.Fatal("native item panel did not prepare")
	}
	screen := ebiten.NewImage(640, 400)
	if !g.drawNativeItemPanel(screen) {
		t.Fatal("native item panel frame 11 did not draw")
	}
	if g.itemAnimStep != 0 {
		t.Fatalf("initial animation step=%d", g.itemAnimStep)
	}
	for step := 0; step < 11; step++ {
		if !g.stepNativeItemPanelAnimation() {
			t.Fatalf("opening step %d did not block input", step)
		}
	}
	if g.itemAnimStep != 11 || g.stepNativeItemPanelAnimation() {
		t.Fatalf("opened animation step=%d", g.itemAnimStep)
	}
	g.beginNativeItemPanelClose()
	if !g.itemClosing || g.itemAnimStep != 0 {
		t.Fatalf("closing state=%v/%d", g.itemClosing, g.itemAnimStep)
	}
	for step := 0; step < 12; step++ {
		if !g.stepNativeItemPanelAnimation() {
			t.Fatalf("closing step %d did not block input", step)
		}
	}
	if g.itemOpen || !g.ring || g.nativeItemPanel != nil {
		t.Fatalf("closed state item=%v ring=%v panel=%v", g.itemOpen, g.ring, g.nativeItemPanel)
	}
}

func TestCampaignChapterOnePartyPreparesNativeItemPanel(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2/"
	for _, name := range []string{"FDOTHER.DAT", "FDTXT.DAT", "DATO.DAT"} {
		if _, err := os.Stat(base + name); err != nil {
			t.Skip("player-provided original archives are absent")
		}
	}
	sc, err := battle.LoadScenario("../../assets/scenarios/ch01.json")
	if err != nil {
		t.Fatal(err)
	}
	units := sc.PartyUnits(nil)
	if len(units) == 0 {
		t.Fatal("chapter one has no party")
	}
	unit := units[0]
	if _, err := battle.NativeItemPanelRecordForUnit(unit); err != nil {
		t.Fatalf("normal campaign party lacks native item-panel provenance: %v", err)
	}
	t.Setenv("FD2_ORIGINAL_FDOTHER", base+"FDOTHER.DAT")
	t.Setenv("FD2_ORIGINAL_FDTXT", base+"FDTXT.DAT")
	t.Setenv("FD2_ORIGINAL_DATO", base+"DATO.DAT")
	g := &Game{sel: unit, itemOpen: true, nativeUIPalette: loadNativeUIPalette()}
	if !g.prepareNativeItemPanel(unit) || g.nativeItemPanel == nil {
		t.Fatal("normal campaign party did not prepare native item panel")
	}
}

func TestApplyNativeImmediateItemUsesTwoStageSelfTargetAndEndsAction(t *testing.T) {
	unit := nativeItemPanelTestUnit()
	unit.Inventory = []int{198, 0x20}
	unit.Equipped = []bool{false, true}
	unit.InventorySlots = []int{198, 0x20, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}
	unit.NativeInventoryFlags = []int{0, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80}
	unit.OnField, unit.EquipmentBaseSet, unit.BaseAP = true, true, 20
	g := &Game{
		st: &battle.State{
			W: 1, H: 1, Units: []*battle.Unit{unit},
			NativeTargetFlags: []byte{0},
		},
		sel: unit, moved: true, itemOpen: true,
		shopItemStats: map[int]campaign.ItemStats{0x20: {AP: 2}},
	}
	var err error
	g.nativeItemEffectRows, err = battle.LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	applied, err := g.applyNativeImmediateItem(0, 198)
	if err != nil || !applied {
		t.Fatalf("applied=%v err=%v", applied, err)
	}
	if unit.BaseAP != 29 || unit.AP != 31 || !unit.Acted ||
		!unit.HasNativeRecordByte5 || unit.NativeRecordByte5&0x80 == 0 ||
		len(unit.Inventory) != 1 || unit.Inventory[0] != 0x20 ||
		g.sel != nil || g.itemOpen || g.moved {
		t.Fatalf("native immediate item transaction incomplete: unit=%#v game=%#v", unit, g)
	}
}

func TestApplyNativeImmediateCapacityItemKeepsCurrentHP(t *testing.T) {
	unit := nativeItemPanelTestUnit()
	unit.HP, unit.MaxHP = 40, 100
	unit.Inventory = []int{94}
	unit.Equipped = []bool{false}
	unit.InventorySlots = []int{94, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}
	unit.NativeInventoryFlags = []int{0, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80}
	unit.OnField = true
	g := &Game{
		st: &battle.State{
			W: 1, H: 1, Units: []*battle.Unit{unit},
			NativeTargetFlags: []byte{0},
		},
		sel: unit, moved: true, itemOpen: true,
	}
	var err error
	g.nativeItemEffectRows, err = battle.LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	applied, err := g.applyNativeImmediateItem(0, 94)
	if err != nil || !applied {
		t.Fatalf("applied=%v err=%v", applied, err)
	}
	if unit.HP != 40 || unit.MaxHP != 120 || len(unit.Inventory) != 0 ||
		!unit.Acted || unit.NativeRecordByte5&0x80 == 0 || g.sel != nil {
		t.Fatalf("native capacity item transaction incomplete: unit=%#v", unit)
	}
}

func TestNativeHPRestoreTargetTransactionUsesProcessRNGAndConsumesSource(t *testing.T) {
	actor := nativeItemPanelTestUnit()
	actor.X, actor.Y, actor.OnField = 1, 1, true
	actor.NativeRecordByte5, actor.HasNativeRecordByte5 = 0, true
	actor.Inventory = []int{192}
	actor.Equipped = []bool{false}
	actor.InventorySlots = []int{192, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff}
	actor.NativeInventoryFlags = []int{0, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80}

	target := nativeItemPanelTestUnit()
	target.X, target.Y, target.OnField = 1, 2, true
	target.NativeIdentity = 1
	target.NativeRecordByte5, target.HasNativeRecordByte5 = 0, true
	target.HP, target.MaxHP = 20, 100

	g := &Game{
		st: &battle.State{
			W: 3, H: 3, Units: []*battle.Unit{actor, target},
			NativeTargetFlags: make([]byte, 9),
		},
		sel: actor, moved: true, itemOpen: true,
	}
	var err error
	g.nativeItemEffectRows, err = battle.LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	targeting, err := g.beginNativeRestoreItem(0, 192)
	if err != nil || !targeting || !g.nativeItemTargeting || g.itemOpen {
		t.Fatalf("targeting=%v state=%v itemOpen=%v err=%v", targeting, g.nativeItemTargeting, g.itemOpen, err)
	}
	candidates := g.nativeItemSelectionTargets()
	foundTarget := false
	for _, candidate := range candidates {
		foundTarget = foundTarget || candidate == target
	}
	if !foundTarget {
		t.Fatalf("native item selection candidates=%v", candidates)
	}
	applied, err := g.applyNativeRestoreItem(target)
	if err != nil || !applied {
		t.Fatalf("applied=%v err=%v", applied, err)
	}
	wantState := fdother.NativeRNGStep(0)
	wantHP := 20 + 40*9/10 + int(wantState%100)*40/1000
	if target.HP != wantHP || g.nativeRNGState != wantState ||
		len(actor.Inventory) != 0 || actor.NativeInventoryFlags[0]&0x80 == 0 ||
		!actor.Acted || actor.NativeRecordByte5&0x80 == 0 ||
		g.sel != nil || g.nativeItemTargeting {
		t.Fatalf("native HP transaction actor=%#v targetHP=%d rng=%#x game=%#v", actor, target.HP, g.nativeRNGState, g)
	}
}
