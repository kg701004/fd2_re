package campaign

import (
	"math/rand"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func TestLoadReviveFeeRatesUsesExportedEXETable(t *testing.T) {
	rates, err := LoadReviveFeeRates(filepath.Join("..", "..", "..", "docs", "data", "exe_tables", "revive_fee_rates.json"))
	if err != nil {
		t.Fatal(err)
	}
	if len(rates) != 29 || rates[0] != 506 || rates[9] != 1200 || rates[25] != 350 {
		t.Fatalf("unexpected fee table length/values: len=%d rates=%v", len(rates), rates)
	}
}

func TestAdvanceNativeChurchServiceSelectionWrapsLeftRight(t *testing.T) {
	tests := []struct {
		current, delta, want int
	}{
		{0, -1, 3},
		{3, 1, 0},
		{1, -1, 0},
		{2, 1, 3},
		{99, 1, 1},
		{-1, -1, 3},
		{2, 0, 2},
	}
	for _, tc := range tests {
		if got := AdvanceNativeChurchServiceSelection(tc.current, tc.delta); got != tc.want {
			t.Fatalf("selection current=%d delta=%d got=%d want=%d", tc.current, tc.delta, got, tc.want)
		}
	}
}

func TestAdvanceNativeTwoColumnSelectionIsBounded(t *testing.T) {
	tests := []struct {
		current, count, delta, want int
	}{
		{0, 8, -1, 0},
		{0, 8, -2, 0},
		{1, 8, 1, 2},
		{2, 8, -2, 0},
		{6, 8, 2, 6},
		{5, 8, 2, 7},
		{7, 8, 1, 7},
		{99, 2, -1, 1},
	}
	for _, tc := range tests {
		if got := AdvanceNativeTwoColumnSelection(tc.current, tc.count, tc.delta); got != tc.want {
			t.Fatalf("two-column current=%d count=%d delta=%d got=%d want=%d", tc.current, tc.count, tc.delta, got, tc.want)
		}
	}
}

func TestReviveUnitUsesLevelFeeAndRestoresNativeFields(t *testing.T) {
	u := &battle.Unit{Fig: 9, Lv: 4, HP: 0, MaxHP: 37, OnField: false, NativeRecordByte5: 1, HasNativeRecordByte5: true}
	gold, cost, err := ReviveUnit(321, u, 7)
	if err != nil || cost != 28 || gold != 293 {
		t.Fatalf("revive result gold=%d cost=%d err=%v", gold, cost, err)
	}
	if u.HP != 37 || !u.OnField {
		t.Fatalf("revive fields hp=%d on_field=%v", u.HP, u.OnField)
	}
}

func TestReviveUnitIsAtomicOnInsufficientGoldOrInvalidCandidate(t *testing.T) {
	dead := &battle.Unit{Lv: 4, HP: 0, MaxHP: 37, OnField: false, NativeRecordByte5: 1, HasNativeRecordByte5: true}
	if gold, cost, err := ReviveUnit(27, dead, 7); err == nil || gold != 27 || cost != 28 || dead.HP != 0 || dead.OnField {
		t.Fatalf("insufficient-gold mutation gold=%d cost=%d err=%v unit=%#v", gold, cost, err, dead)
	}
	alive := &battle.Unit{Lv: 4, HP: 1, MaxHP: 37, OnField: true, NativeRecordByte5: 0, HasNativeRecordByte5: true}
	if gold, cost, err := ReviveUnit(100, alive, 7); err == nil || gold != 100 || cost != 0 || alive.HP != 1 {
		t.Fatalf("alive candidate mutation gold=%d cost=%d err=%v unit=%#v", gold, cost, err, alive)
	}
	legacyDead := &battle.Unit{Lv: 4, HP: 0, MaxHP: 37}
	if CanRevive(legacyDead) {
		t.Fatal("HP projection without raw byte5 provenance must fail closed")
	}
}

func TestReviveUnitUsesRawLevelWithoutInventedMinimum(t *testing.T) {
	u := &battle.Unit{
		Lv: 0, HP: 0, MaxHP: 9,
		NativeRecordByte5: 1, HasNativeRecordByte5: true,
	}
	gold, cost, err := ReviveUnit(12, u, 7)
	if err != nil || gold != 12 || cost != 0 || u.HP != 9 || u.NativeRecordByte5&1 != 0 {
		t.Fatalf("level-zero raw revive gold=%d cost=%d err=%v unit=%#v", gold, cost, err, u)
	}
}

func TestClassChangeCandidatesMatchOriginal31793Predicate(t *testing.T) {
	roster := map[int]battle.Unit{
		0:  {Fig: 0, Lv: 20, Portrait: 0},
		9:  {Fig: 9, Lv: 19, Portrait: 9},
		4:  {Fig: 4, Lv: 20, Portrait: 7},
		30: {Fig: 30, Lv: 20, Portrait: 18},
	}
	got := ClassChangeCandidates(roster, []int{0, 9, 4, 30})
	if len(got) != 1 || got[0] != 0 {
		t.Fatalf("class change candidates=%v, want [0]", got)
	}
}

func TestNativeClassConfirmationUsesLeftRightWithoutWrap(t *testing.T) {
	if got := AdvanceNativeClassConfirmation(1, -1); got != 0 {
		t.Fatalf("left=%d want 0", got)
	}
	if got := AdvanceNativeClassConfirmation(0, 1); got != 1 {
		t.Fatalf("right=%d want 1", got)
	}
	if got := AdvanceNativeClassConfirmation(1, 0); got != 1 {
		t.Fatalf("no input=%d want 1", got)
	}
}

func TestNativeClassCandidateWindowShowsThreeRowsAndScrolls(t *testing.T) {
	tests := []struct {
		count, selected int
		start, visible  int
	}{
		{0, 0, 0, 0},
		{2, 1, 0, 2},
		{5, 0, 0, 3},
		{5, 2, 0, 3},
		{5, 3, 1, 3},
		{5, 4, 2, 3},
	}
	for _, tt := range tests {
		start, visible := NativeClassCandidateWindow(tt.count, tt.selected)
		if start != tt.start || visible != tt.visible {
			t.Fatalf("window(%d,%d)=(%d,%d), want (%d,%d)", tt.count, tt.selected, start, visible, tt.start, tt.visible)
		}
	}
}

func TestNativeThreeRowWindowPreservesStatefulOrigin(t *testing.T) {
	start := 0
	for _, step := range []struct {
		selected, want int
	}{
		{0, 0}, {2, 0}, {3, 1}, {4, 2}, {3, 2}, {1, 1}, {0, 0},
	} {
		var visible int
		start, visible = NativeThreeRowWindow(6, step.selected, start)
		if start != step.want || visible != 3 {
			t.Fatalf("selected%d window=(%d,%d), want (%d,3)", step.selected, start, visible, step.want)
		}
	}
}

func TestApplyClassChangeAddsGrowthAndConsumesItem(t *testing.T) {
	u := &battle.Unit{Fig: 9, Portrait: 9, BattleFig: 9, MapSelectorKey: 9, HasMapSelectorKey: true, MapSelectorSlot: 3, HasMapSelectorSlot: true, ClassID: 5, NativeRecordRace: 1, HasNativeRecordRace: true, NativeRecordClass: 5, HasNativeRecordClass: true, Lv: 27, Exp: 73, AP: 99, DP: 88, DX: 77, MV: 5,
		Inventory: []int{0x5a, 0x20}, Equipped: []bool{true, false}, InventorySlots: []int{0x5a, 0x20}}
	row := ClassChangeGrowth{AP: [2]int{10, 11}, DP: [2]int{20, 21}, DX: [2]int{30, 31}, HP: [2]int{40, 41}, MP: [2]int{50, 51}}
	if err := ApplyClassChange(u, 0x34, 21, 2, row, rand.New(rand.NewSource(1)), 0); err != nil {
		t.Fatal(err)
	}
	if u.AP != 109 || u.DP != 108 || u.DX != 107 || u.MaxHP != 40 || u.HP != 40 || u.MaxMP != 50 || u.MP != 50 {
		t.Fatalf("incremented stats AP/DP/DX=%d/%d/%d HP=%d/%d MP=%d/%d", u.AP, u.DP, u.DX, u.HP, u.MaxHP, u.MP, u.MaxMP)
	}
	if u.Lv != 27 || u.Exp != 0 || u.MV != 7 || u.Portrait != 0x34 || u.ClassID != 21 {
		t.Fatalf("metadata lv=%d exp=%v mv=%d portrait=%x class=%d", u.Lv, u.Exp, u.MV, u.Portrait, u.ClassID)
	}
	if u.Fig != 9 || u.BattleFig != 0x34 || !u.HasMapSelectorKey || u.MapSelectorKey != 0x34 || u.HasMapSelectorSlot {
		t.Fatalf("class-change selectors fig=%d battle=%d key=%d known=%v slot-known=%v", u.Fig, u.BattleFig, u.MapSelectorKey, u.HasMapSelectorKey, u.HasMapSelectorSlot)
	}
	if !u.HasNativeRecordRace || u.NativeRecordRace != 1 || !u.HasNativeRecordClass || u.NativeRecordClass != 21 {
		t.Fatalf("class-change raw race/class=%d/%d known=%v/%v", u.NativeRecordRace, u.NativeRecordClass, u.HasNativeRecordRace, u.HasNativeRecordClass)
	}
	if len(u.Inventory) != 1 || u.Inventory[0] != 0x20 || u.Equipped[0] {
		t.Fatalf("item removal inventory=%v equipped=%v", u.Inventory, u.Equipped)
	}
}

func TestApplyClassChangeRejectsInvalidRangeAtomically(t *testing.T) {
	u := &battle.Unit{Lv: 20, AP: 7, Inventory: []int{9}}
	err := ApplyClassChange(u, 0x20, 9, 1, ClassChangeGrowth{AP: [2]int{2, 1}}, rand.New(rand.NewSource(1)), 0)
	if err == nil || u.AP != 7 || len(u.Inventory) != 1 {
		t.Fatalf("invalid range mutated unit: err=%v unit=%+v", err, u)
	}
}
