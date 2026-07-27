package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func TestNativeItemMenuSlotPreservesEightRawCells(t *testing.T) {
	g := &Game{}
	u := &battle.Unit{
		Inventory:            []int{0x10, 0x20},
		InventorySlots:       []int{0x10, 0xff, 0x20, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0, 0x80, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	if ok, id := g.nativeItemMenuSlot(u, 1); ok || id != 0xff {
		t.Fatalf("raw empty slot moved or became occupied: ok=%v id=%02x", ok, id)
	}
	if ok, id := g.nativeItemMenuSlot(u, 2); !ok || id != 0x20 {
		t.Fatalf("raw equipped slot lost: ok=%v id=%02x", ok, id)
	}
}

func TestNativeItemMenuSlotLegacyFallbackIsCompactAndBounded(t *testing.T) {
	g := &Game{}
	u := &battle.Unit{Inventory: []int{0x34}}
	if ok, id := g.nativeItemMenuSlot(u, 0); !ok || id != 0x34 {
		t.Fatalf("legacy first item unavailable: ok=%v id=%02x", ok, id)
	}
	if ok, _ := g.nativeItemMenuSlot(u, 1); ok {
		t.Fatal("legacy selector fabricated an item beyond inventory")
	}
	if ok, _ := g.nativeItemMenuSlot(u, 8); ok {
		t.Fatal("selector accepted out-of-range slot")
	}
}
