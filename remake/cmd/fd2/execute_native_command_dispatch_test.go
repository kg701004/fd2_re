package main

import (
	"strings"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

// TestExecuteNativeCommandTargetDispatchesIDsOneThroughTwelve covers the
// 2026-08-17 fix for #113: executeNativeCommandTarget's switch never had a
// case for command IDs 1..12 (only id==0 was special-cased), even though
// ExecuteNativeCommandDamage's own doc comment already covers "player-
// dispatched command IDs 0..12" byte-for-byte. Every AI-chosen spell/command
// in that range (confirmed live via TestSweepNativeAIWinnersAcrossAllChapters:
// ch21 picked id=2, ch25/ch30 picked id=12) fell into the default case and
// failed with "native command target executor unavailable", even though the
// executor underneath was already implemented and tested. This only proves
// the dispatch reaches ExecuteNativeCommandDamage (error is no longer the
// "unavailable" default-case message) -- it does not assert a successful
// cast, since real IDs 2/12 also surface separate, unrelated gaps (an AI
// scoring anomaly for id 12's self-target case, and a missing resistance
// table entry for one specific enemy class in ch21) documented in
// 58-remake-live-verification-log.md's #113 section, not fixed by this
// dispatch wiring alone.
func TestExecuteNativeCommandTargetDispatchesIDsOneThroughTwelve(t *testing.T) {
	book := make([]battle.NativeCommandRecord, battle.NativeCommandRecordCount)
	for id := range book {
		book[id] = battle.NativeCommandRecord{ID: id}
	}
	book[2] = battle.NativeCommandRecord{ID: 2, Damage: 250, Hit: 90, SelectionMode: 5, EffectMode: 1, MPCost: 20, TargetCode: 0}
	book[12] = battle.NativeCommandRecord{ID: 12, Damage: 340, Hit: 90, SelectionMode: 5, EffectMode: 1, MPCost: 80, TargetCode: 0}

	for _, id := range []int{1, 2, 5, 12} {
		actor := &battle.Unit{Camp: battle.Own, OnField: true, HP: 20, MP: 100, X: 0, Y: 0, HasNativeRecordByte6: true, NativeRecordByte6: 2}
		target := &battle.Unit{Camp: battle.Enemy, ClassID: 5, OnField: true, HP: 500, X: 1, Y: 0}
		st := &battle.State{
			W: 2, H: 1, Units: []*battle.Unit{actor, target},
			NativeCompositionEventBytes: make([]byte, 2),
			NativeCommandBook:           book,
			NativeCommandResistances:    map[int]int{5: 10},
		}
		g := &Game{st: st}
		_, _, err := g.executeNativeCommandTarget(actor, target, id, nil)
		if err != nil && strings.Contains(err.Error(), "executor unavailable") {
			t.Fatalf("id=%d still falls into the unimplemented-executor default case: %v", id, err)
		}
	}
}
