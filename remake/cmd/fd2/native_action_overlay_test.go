package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestNativeActionOffsetXYMatchesFinalOpenFrame(t *testing.T) {
	offsets, err := fdother.ActionOverlayFrameOffsets(3, false)
	if err != nil {
		t.Fatal(err)
	}
	want := [4][2]int{{0, -13}, {-18, 2}, {18, 2}, {0, 17}}
	for direction, offset := range offsets {
		x, y := nativeActionOffsetXY(offset)
		if got := [2]int{x, y}; got != want[direction] {
			t.Fatalf("direction %d offset=%#x gives %v, want %v", direction, offset, got, want[direction])
		}
	}
}

func TestActionOverlayAvailabilityUsesCurrentRemakeGates(t *testing.T) {
	g := &Game{st: &battle.State{}, sel: &battle.Unit{Spells: []int{1}, Inventory: []int{2}}}
	if got := g.actionOverlayAvailability(); got != [4]int{1, 0, 0, 0} {
		t.Fatalf("availability=%v", got)
	}
	g.sel.Sealed = true
	g.sel.Inventory = nil
	if got := g.actionOverlayAvailability(); got != [4]int{1, 1, 1, 0} {
		t.Fatalf("availability=%v", got)
	}
}

func TestActionOverlayAvailabilityRequiresRecoveredNativeInventoryGates(t *testing.T) {
	selected := battle.Unit{OnField: true, HP: 10, AtkMin: 1, AtkMax: 1, Inventory: []int{3}, Equipped: []bool{false}}
	enemy := &battle.Unit{OnField: true, HP: 10, Camp: battle.Enemy, X: 1, Y: 0}
	g := &Game{st: &battle.State{Units: []*battle.Unit{enemy}}, sel: &selected}
	if got := g.actionOverlayAvailability(); got != [4]int{1, 1, 0, 0} {
		t.Fatalf("without equipped weapon/raw command availability=%v", got)
	}
	selected.Equipped[0] = true
	selected.NativeCommandMask[0] = 0x01
	if got := g.actionOverlayAvailability(); got != [4]int{0, 0, 0, 0} {
		t.Fatalf("with equipped weapon/raw command availability=%v", got)
	}
}

func TestActionOverlayNativeCommandGateUsesRawOffset27NotLegacySeal(t *testing.T) {
	selected := battle.Unit{
		OnField: true, HP: 10, AtkMin: 1, AtkMax: 1,
		Inventory: []int{3}, Equipped: []bool{true},
		NativeCommandMask: [5]byte{1},
	}
	enemy := &battle.Unit{OnField: true, HP: 10, Camp: battle.Enemy, X: 1, Y: 0}
	g := &Game{st: &battle.State{Units: []*battle.Unit{enemy}}, sel: &selected}
	selected.Sealed = true // normalized legacy state is not the native +0x27 gate.
	if got := g.actionOverlayAvailability(); got != [4]int{0, 0, 0, 0} {
		t.Fatalf("legacy seal must not disable raw command: availability=%v", got)
	}
	selected.NativeTransient[5] = 1 // exact raw unit+0x27.
	if got := g.actionOverlayAvailability(); got != [4]int{0, 1, 0, 0} {
		t.Fatalf("raw +0x27 must disable command: availability=%v", got)
	}
}
