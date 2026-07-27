package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func TestApplyPersistentStatsPreservesDynamicNativeCommandMask(t *testing.T) {
	dst := &battle.Unit{NativeCommandMask: [5]byte{1, 2, 3, 4, 5}}
	src := &battle.Unit{
		NativeCommandMask: [5]byte{0x81, 0x01, 0, 0x80, 0x11},
		NativeIdentity:    9, HasNativeIdentity: true,
		NativeRecordRace: 1, HasNativeRecordRace: true,
		NativeRecordClass: 5, HasNativeRecordClass: true,
		NativeTransient:   [6]byte{1, 2, 3, 4, 5, 6},
		NativeRecordByte5: 1, HasNativeRecordByte5: true,
		NativeRecordByte6: 7, HasNativeRecordByte6: true,
		NativeRecordWord42: 0x140, HasNativeRecordWord42: true,
		NativeInventoryFlags: []int{0x40, 0x40, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	applyPersistentStats(dst, src)
	if got, want := dst.NativeCommandMask, src.NativeCommandMask; got != want {
		t.Fatalf("persistent native command mask=%v want %v", got, want)
	}
	if dst.NativeRecordByte5 != 1 || !dst.HasNativeRecordByte5 || dst.NativeRecordByte6 != 7 || !dst.HasNativeRecordByte6 {
		t.Fatalf("persistent raw record bytes not preserved: byte5=%#x/%v byte6=%#x/%v", dst.NativeRecordByte5, dst.HasNativeRecordByte5, dst.NativeRecordByte6, dst.HasNativeRecordByte6)
	}
	if dst.NativeRecordWord42 != 0x140 || !dst.HasNativeRecordWord42 {
		t.Fatalf("persistent raw +0x42 not preserved: word=%#x/%v", dst.NativeRecordWord42, dst.HasNativeRecordWord42)
	}
	if dst.NativeIdentity != 9 || !dst.HasNativeIdentity ||
		dst.NativeRecordRace != 1 || !dst.HasNativeRecordRace ||
		dst.NativeRecordClass != 5 || !dst.HasNativeRecordClass ||
		dst.NativeTransient != src.NativeTransient ||
		len(dst.NativeInventoryFlags) != 8 || dst.NativeInventoryFlags[0] != 0x40 {
		t.Fatalf("persistent raw item-panel provenance not preserved: %#v", dst)
	}
}

func TestSyncPartyUsesRawByte5ForHPRefill(t *testing.T) {
	g := &Game{
		st:           &battle.State{Units: []*battle.Unit{{Fig: 0, Camp: battle.Own, OnField: false, HP: 0, MaxHP: 50, MP: 2, MaxMP: 8, HasNativeRecordByte5: true, NativeRecordByte5: 0}}},
		partyMembers: map[int]bool{0: true}, partyRoster: map[int]battle.Unit{0: {Fig: 0, Camp: battle.Own, MaxHP: 50, MaxMP: 8}},
	}
	if err := g.syncPartyFromBattle(); err != nil {
		t.Fatal(err)
	}
	if got := g.partyRoster[0].HP; got != 50 {
		t.Fatalf("raw byte5=0 did not refill HP: got %d", got)
	}

	g.st.Units[0].NativeRecordByte5 = 1
	g.st.Units[0].HP = 0
	if err := g.syncPartyFromBattle(); err != nil {
		t.Fatal(err)
	}
	if got := g.partyRoster[0].HP; got != 0 {
		t.Fatalf("raw byte5=1 incorrectly refilled HP: got %d", got)
	}
}
