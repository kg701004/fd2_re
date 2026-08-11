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

func TestNativeCommandGridWindowKeepsSmallListsUnscrolled(t *testing.T) {
	start, visible := NativeCommandGridWindow(5, 2, 0)
	if start != 0 || visible != 5 {
		t.Fatalf("small list should not scroll: start=%d visible=%d", start, visible)
	}
}

func TestNativeCommandGridWindowScrollsFullThirtySixCommands(t *testing.T) {
	// A unit holding all 36 defined commands: selecting the last one must
	// scroll the window forward by whole columns (multiples of 4).
	start, visible := NativeCommandGridWindow(36, 35, 0)
	if start%NativeCommandGridRows != 0 {
		t.Fatalf("scrolled start must stay column-aligned: start=%d", start)
	}
	if visible != NativeCommandGridVisible {
		t.Fatalf("full window should show all %d visible slots, got %d", NativeCommandGridVisible, visible)
	}
	if 35 < start || 35 >= start+visible {
		t.Fatalf("selected index 35 must be inside the window: start=%d visible=%d", start, visible)
	}

	// Selecting back near the front must scroll back to the start.
	start, visible = NativeCommandGridWindow(36, 0, start)
	if start != 0 || visible != NativeCommandGridVisible {
		t.Fatalf("scrolling back to index 0: start=%d visible=%d", start, visible)
	}
}

func TestNativeCommandGridWindowRejectsInvalidInputs(t *testing.T) {
	if start, visible := NativeCommandGridWindow(0, 0, 0); start != 0 || visible != 0 {
		t.Fatalf("empty list: start=%d visible=%d", start, visible)
	}
	if start, visible := NativeCommandGridWindow(5, 5, 0); start != 0 || visible != 0 {
		t.Fatalf("out-of-range selected: start=%d visible=%d", start, visible)
	}
	if start, visible := NativeCommandGridWindow(5, 0, 1); start != 0 || visible != 0 {
		t.Fatalf("non-column-aligned start must fail closed: start=%d visible=%d", start, visible)
	}
}
