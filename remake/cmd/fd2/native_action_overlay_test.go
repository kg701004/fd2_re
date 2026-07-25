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
