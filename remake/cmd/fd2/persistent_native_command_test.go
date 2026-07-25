package main

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func TestApplyPersistentStatsPreservesDynamicNativeCommandMask(t *testing.T) {
	dst := &battle.Unit{NativeCommandMask: [5]byte{1, 2, 3, 4, 5}}
	src := &battle.Unit{NativeCommandMask: [5]byte{0x81, 0x01, 0, 0x80, 0x11}}
	applyPersistentStats(dst, src)
	if got, want := dst.NativeCommandMask, src.NativeCommandMask; got != want {
		t.Fatalf("persistent native command mask=%v want %v", got, want)
	}
}
