package battle

import "testing"

func TestNativeCommandGridMatchesRecoveredFourRowLayout(t *testing.T) {
	grid := NativeCommandGrid([]int{0, 1, 2, 3, 4}, 4)
	if got := grid[0]; got.X != 0x12 || got.Y != 0x67 || got.Column != 0 || got.Row != 0 || got.Selected {
		t.Fatalf("first cell=%+v", got)
	}
	if got := grid[4]; got.X != 0x76 || got.Y != 0x67 || got.Column != 1 || got.Row != 0 || !got.Selected {
		t.Fatalf("fifth cell=%+v", got)
	}
}

func TestNativeCommandGridMoveMatchesOriginalBounds(t *testing.T) {
	if got := NativeCommandGridMove(0, 6, 0); got != 5 {
		t.Fatalf("up wrap=%d", got)
	}
	if got := NativeCommandGridMove(5, 6, 1); got != 0 {
		t.Fatalf("down wrap=%d", got)
	}
	if got := NativeCommandGridMove(1, 6, 2); got != 1 {
		t.Fatalf("left edge=%d", got)
	}
	if got := NativeCommandGridMove(1, 6, 3); got != 5 {
		t.Fatalf("right=%d", got)
	}
	if got := NativeCommandGridMove(5, 6, 3); got != 5 {
		t.Fatalf("right bound=%d", got)
	}
}

func TestNativeCommandGridMissingInputsRemainInert(t *testing.T) {
	if got := NativeCommandGrid(nil, 0); got == nil || len(got) != 0 {
		t.Fatalf("empty command ids=%#v, want non-nil empty grid", got)
	}
	ids := []int{0, 7}
	for _, selected := range []int{-1, len(ids), 99} {
		grid := NativeCommandGrid(ids, selected)
		if len(grid) != len(ids) {
			t.Fatalf("selected=%d changed grid length=%d", selected, len(grid))
		}
		for i, cell := range grid {
			if cell.Selected {
				t.Fatalf("selected=%d marked cell %d despite out-of-range selection", selected, i)
			}
		}
	}
}
