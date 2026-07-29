package main

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func nativeEvent61PlayerGame(t *testing.T, items ...int) (*Game, *battle.Unit) {
	t.Helper()
	fdotherPath, err := filepath.Abs(
		"../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT",
	)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT unavailable")
	}
	t.Setenv("FD2_MUTE", "1")
	t.Setenv("FD2_CAMPAIGN", "assets/scenarios/campaign_full.json")
	t.Setenv("FD2_CAMP_NODE", "battle_ch26")
	t.Setenv("FD2_ORIGINAL_FDOTHER", fdotherPath)
	g := loadGame()
	if g.loadErr != "" {
		t.Fatal(g.loadErr)
	}
	if g.st == nil || len(g.st.Units) == 0 {
		t.Fatal("chapter26 battle state unavailable")
	}
	trigger := g.st.Units[0]
	trigger.X, trigger.Y = 1, 46
	trigger.NativeRecordWord42 = uint16(trigger.MaxHP)
	trigger.HasNativeRecordWord42 = true
	trigger.Inventory = append([]int(nil), items...)
	trigger.Equipped = make([]bool, len(items))
	trigger.InventorySlots = make([]int, 8)
	trigger.NativeInventoryFlags = make([]int, 8)
	for i := range trigger.InventorySlots {
		trigger.InventorySlots[i] = 0xff
		trigger.NativeInventoryFlags[i] = 0x80
	}
	for i, item := range items {
		trigger.InventorySlots[i] = item
		trigger.NativeInventoryFlags[i] = 0
	}
	g.sel, g.curX, g.curY = trigger, 1, 46
	g.selOrigX, g.selOrigY = 1, 46
	g.moved = true
	return g, trigger
}

func TestNativeEvent61MissingItemRunsOnlyEditableFDTXT2(t *testing.T) {
	g, trigger := nativeEvent61PlayerGame(t, 0x20)
	g.finishSelectedWait()
	if g.battleEvent == nil || len(g.dialog) != 1 ||
		g.dialog[0].Text != "那是什麼奇怪的東西?頭部還開著?" {
		t.Fatalf("missing item dialogue=%#v run=%#v", g.dialog, g.battleEvent)
	}
	if g.nativeFieldEvent61 != nil || g.st.NativeEventState[12] != 0 ||
		!reflect.DeepEqual(trigger.Inventory, []int{0x20}) {
		t.Fatal("missing item path mutated or started presentation")
	}
	g.dialog = nil
	g.advanceBattleEvent()
	if g.battleEvent != nil || g.sel != nil || !trigger.Acted {
		t.Fatal("missing item path did not finish the successful wait action")
	}
}

func TestNativeEvent61MaterializedRuntimePresentsCommitsAndPersistsWold(t *testing.T) {
	g, trigger := nativeEvent61PlayerGame(t, 0xD0, 0x20)
	// battle_ch26 does not yet carry a proven native_map_view/native_map_hud
	// campaign boundary. Materialize the event-local state explicitly so this
	// test covers the presentation/transaction adapter without upgrading the
	// unmodified player path to E2.
	if err := g.st.MaterializeNativeMapViewState(battle.NativeMapViewState{
		CameraX: 0, CameraY: 39,
		CursorX: 1, CursorY: 46,
		VisibleCursorX: 1, VisibleCursorY: 7,
	}); err != nil {
		t.Fatal(err)
	}
	if !g.st.MaterializeNativeMapRangeMode(1) ||
		!g.st.MaterializeNativeMapHUDState(1, 1, 1) {
		t.Fatal("event61 explicit native runtime materialization rejected")
	}
	g.finishSelectedWait()
	if g.battleEvent == nil || len(g.dialog) != 1 ||
		g.dialog[0].Text != "這機兵的頭部怎麼開著?這個金屬盒子..好像滿適合的,應該是這樣放進去.....咦!" {
		t.Fatalf("success dialogue3=%#v run=%#v", g.dialog, g.battleEvent)
	}
	g.dialog = nil
	g.advanceBattleEvent()
	job := g.nativeFieldEvent61
	if job == nil || len(job.frames) != 59 || job.frame != 0 {
		t.Fatalf("event61 job=%#v loadErr=%q", job, g.loadErr)
	}
	for frame := 0; frame < 59; frame++ {
		if g.nativeFieldEvent61 == nil ||
			g.nativeFieldEvent61.frame != frame {
			t.Fatalf("frame %d job=%#v", frame, g.nativeFieldEvent61)
		}
		g.nativeFieldEvent61.drawn = true
		if !g.nativeFieldEvent61.hasTick {
			g.stepNativeFieldEvent61Tick(100)
		}
		g.stepNativeFieldEvent61Tick(102 + frame*2)
	}
	if g.nativeFieldEvent61 != nil || g.st.NativeEventState[12] != 1 ||
		!reflect.DeepEqual(trigger.Inventory, []int{0x20}) ||
		!g.partyMembers[31] || len(g.partyJoinOrder) == 0 ||
		g.partyJoinOrder[len(g.partyJoinOrder)-1] != 31 {
		t.Fatalf(
			"commit state=%d inventory=%v members=%v order=%v job=%#v",
			g.st.NativeEventState[12], trigger.Inventory,
			g.partyMembers, g.partyJoinOrder, g.nativeFieldEvent61,
		)
	}
	if _, ok := g.partyRoster[31]; !ok {
		t.Fatal("JOIN31 did not persist the materialized Wold record")
	}
	if g.battleEvent == nil || len(g.dialog) != 1 {
		t.Fatalf("FDTXT4 did not begin: run=%#v dialog=%#v", g.battleEvent, g.dialog)
	}
	for g.battleEvent != nil {
		g.dialog = nil
		g.advanceBattleEvent()
	}
	if g.sel != nil || !trigger.Acted {
		t.Fatal("final FDTXT4 did not return to the completed wait action")
	}
}
