package battle

import "testing"

func TestNativeCommandTargetCellsFloodFillHonorsRawFlags(t *testing.T) {
	flags := make([]byte, 5)
	flags[1] = NativeCommandGridBlocked
	flags[3] = NativeCommandGridZeroCost
	cells, err := NativeCommandTargetCells(5, 1, Cell{X: 0, Y: 0}, 2, flags)
	if err != nil {
		t.Fatal(err)
	}
	if cells[Cell{X: 1, Y: 0}] || cells[Cell{X: 2, Y: 0}] {
		t.Fatalf("blocked cell leaked through: %v", cells)
	}
	// A zero-cost chain reaches beyond the normal two-step budget.
	flags = make([]byte, 5)
	flags[1], flags[2], flags[3] = NativeCommandGridZeroCost, NativeCommandGridZeroCost, NativeCommandGridZeroCost
	cells, err = NativeCommandTargetCells(5, 1, Cell{}, 1, flags)
	if err != nil || !cells[Cell{X: 4, Y: 0}] {
		t.Fatalf("zero-cost path cells=%v err=%v", cells, err)
	}
}

func TestNativeCommandTargetCellsCrossIgnoresRawFlags(t *testing.T) {
	flags := []byte{NativeCommandGridBlocked, NativeCommandGridBlocked, NativeCommandGridBlocked, NativeCommandGridBlocked, NativeCommandGridBlocked}
	cells, err := NativeCommandTargetCells(5, 1, Cell{X: 2, Y: 0}, 0x12, flags)
	if err != nil || len(cells) != 5 {
		t.Fatalf("cross cells=%v err=%v", cells, err)
	}
}

func TestNativeCommandTargetsMatchesRecoveredCampCodes(t *testing.T) {
	enemy := &Unit{Camp: Enemy, X: 0, Y: 0, HP: 1, OnField: true}
	ally := &Unit{Camp: Ally, X: 1, Y: 0, HP: 1, OnField: true}
	own := &Unit{Camp: Own, X: 2, Y: 0, HP: 1, OnField: true}
	for code, want := range map[int]int{0: 1, 1: 2, 2: 2, 3: 1} {
		got, err := NativeCommandTargets(3, 1, Cell{X: 1, Y: 0}, 2, code, make([]byte, 3), []*Unit{enemy, ally, own})
		if err != nil || len(got) != want {
			t.Fatalf("code=%d got=%d err=%v want=%d", code, len(got), err, want)
		}
	}
}

func TestNativeCommandTargetCellsFailsClosedWithoutRawFlags(t *testing.T) {
	if _, err := NativeCommandTargetCells(2, 2, Cell{}, 1, nil); err == nil {
		t.Fatal("missing raw flags must fail closed")
	}
}

func TestNativeCommandEffectTargetsRequiresOriginalTwoStages(t *testing.T) {
	actor := &Unit{Camp: Own, X: 0, Y: 0, HP: 10, OnField: true}
	confirmed := &Unit{Camp: Enemy, X: 1, Y: 0, HP: 10, OnField: true}
	otherEnemy := &Unit{Camp: Enemy, X: 2, Y: 0, HP: 10, OnField: true}
	units := []*Unit{actor, confirmed, otherEnemy}

	// Generic command: +3=1 chooses the adjacent enemy as center; +4=0
	// resolves the final effect only on that confirmed cell.
	effects, err := NativeCommandEffectTargets(3, 1, actor, confirmed, 1, 0, 0, make([]byte, 3), units)
	if err != nil || len(effects) != 1 || effects[0] != confirmed {
		t.Fatalf("effects=%v err=%v", effects, err)
	}
	if _, err := NativeCommandEffectTargets(3, 1, actor, otherEnemy, 1, 0, 0, make([]byte, 3), units); err == nil {
		t.Fatal("a non-selection candidate must not become the effect origin")
	}
}
