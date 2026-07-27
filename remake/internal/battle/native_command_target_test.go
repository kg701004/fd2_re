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
	for code, want := range map[int][]*Unit{
		0: {enemy},
		1: {ally, own},
		2: {ally},
		3: {own},
	} {
		got, err := NativeCommandTargets(3, 1, Cell{X: 1, Y: 0}, 2, code, make([]byte, 3), []*Unit{enemy, ally, own})
		if err != nil || len(got) != len(want) {
			t.Fatalf("code=%d got=%v err=%v want=%v", code, got, err, want)
		}
		for i := range want {
			if got[i] != want[i] {
				t.Fatalf("code=%d got[%d]=%p want=%p", code, i, got[i], want[i])
			}
		}
	}
}

func TestNativeCursorConfirmationMatches115B6And14742(t *testing.T) {
	enemy := &Unit{Camp: Enemy, X: 1, Y: 0, HasNativeRecordByte5: true}
	ally := &Unit{Camp: Ally, X: 0, Y: 0, HasNativeRecordByte5: true}
	inactive := &Unit{Camp: Enemy, X: 0, Y: 0, HasNativeRecordByte5: true, NativeRecordByte5: 1}
	units := []*Unit{enemy, ally, inactive}

	// targetCode 5 and 0xff cells reject before the 0x14742 count. A
	// non-0xff targetCode 4 accepts before any roster scan.
	if ok, err := NativeCursorConfirmationAllowed(Cell{}, 0, 3, 5, nil); err != nil || ok {
		t.Fatalf("target code 5 reject ok=%v err=%v", ok, err)
	}
	if ok, err := NativeCursorConfirmationAllowed(Cell{}, 0xff, 3, 4, nil); err != nil || ok {
		t.Fatalf("0xff reject ok=%v err=%v", ok, err)
	}
	if ok, err := NativeCursorConfirmationAllowed(Cell{}, 0, 3, 4, nil); err != nil || !ok {
		t.Fatalf("target code 4 accept ok=%v err=%v", ok, err)
	}

	// selector 3 becomes strict radius 2, so the enemy at distance one
	// accepts. Selector 2 becomes radius one, where distance one is excluded.
	if ok, err := NativeCursorConfirmationAllowed(Cell{}, 0, 3, 0, units); err != nil || !ok {
		t.Fatalf("enemy inside strict radius rejected: ok=%v err=%v", ok, err)
	}
	if ok, err := NativeCursorConfirmationAllowed(Cell{}, 0, 2, 0, units); err != nil || ok {
		t.Fatalf("strict radius boundary accepted: ok=%v err=%v", ok, err)
	}
	if ok, err := NativeCursorConfirmationAllowed(Cell{}, 0, 2, 2, units); err != nil || !ok {
		t.Fatalf("code 2 failed to match ally exactly: ok=%v err=%v", ok, err)
	}
}

func TestNativeCursorConfirmationFailsClosedWithoutRawRoster(t *testing.T) {
	if _, err := NativeCursorConfirmationAllowed(Cell{}, 0, 3, 0, []*Unit{{Camp: Enemy}}); err == nil {
		t.Fatal("incomplete raw roster accepted")
	}
	if _, err := NativeCursorConfirmationAllowed(Cell{}, 0, 3, 6, nil); err == nil {
		t.Fatal("relocation target code accepted by generic gate")
	}
}

func TestNativeCommandTargetsPrefersRawByte5Predicate(t *testing.T) {
	// A fully materialized roster follows the recovered 0x14818 byte+5 gate;
	// normalized HP/OnField values must not reintroduce a second predicate.
	usableRaw := &Unit{Camp: Enemy, X: 1, Y: 0, HP: 0, OnField: false, HasNativeRecordByte5: true, NativeRecordByte5: 0}
	inactiveRaw := &Unit{Camp: Enemy, X: 2, Y: 0, HP: 10, OnField: true, HasNativeRecordByte5: true, NativeRecordByte5: 1}
	units := []*Unit{usableRaw, inactiveRaw}
	got, err := NativeCommandTargets(3, 1, Cell{X: 0, Y: 0}, 2, 0, make([]byte, 3), units)
	if err != nil || len(got) != 1 || got[0] != usableRaw {
		t.Fatalf("raw target filter got=%v err=%v", got, err)
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
