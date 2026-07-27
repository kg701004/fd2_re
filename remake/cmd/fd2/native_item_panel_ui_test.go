package main

import (
	"os"
	"testing"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func nativeItemPanelTestUnit() *battle.Unit {
	return &battle.Unit{
		BattleFig: 0, NativeIdentity: 0, HasNativeIdentity: true,
		NativeRecordByte6: 1, HasNativeRecordByte6: true,
		NativeConstructor: &battle.NativeConstructorTable{
			Branch: "high_class", Index: 0,
			Record: []byte{0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
		},
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
