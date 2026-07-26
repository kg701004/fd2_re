package fdother

import "testing"

func TestNativeSplitSlideStepsMatchVerifiedABI(t *testing.T) {
	steps := NativeSplitSlideSteps()
	if len(steps) != 5 {
		t.Fatalf("steps=%d, want 5", len(steps))
	}
	want := [][5]int{{100, -15, 82, 265, 81}, {75, 10, 82, 240, 81}, {50, 35, 82, 215, 81}, {25, 60, 82, 190, 81}, {0, 85, 82, 165, 81}}
	for i, step := range steps {
		got := [5]int{step.Offset, step.LeftX, step.LeftY, step.RightX, step.RightY}
		if got != want[i] {
			t.Fatalf("step %d=%v, want %v", i, got, want[i])
		}
	}
}

func TestRunNativeSplitSlidePreservesPresentRestoreOrder(t *testing.T) {
	cell := LMI1Entry{Width: 2, Height: 1, Pixels: []byte{7, 0}}
	dst := make([]byte, 456*200)
	var events []string
	err := RunNativeSplitSlide(cell, dst, func() error { events = append(events, "present"); return nil }, func() error { events = append(events, "restore"); return nil })
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 10 {
		t.Fatalf("events=%v, want five present/restore pairs", events)
	}
	for i := 0; i < 5; i++ {
		if events[i*2] != "present" || events[i*2+1] != "restore" {
			t.Fatalf("events=%v", events)
		}
	}
	// The last pass is at the unshifted left anchor; transparent zero must
	// preserve the byte immediately to its right.
	if dst[82*456+85] != 7 || dst[82*456+86] != 0 {
		t.Fatalf("last cell pixels=%v,%v", dst[82*456+85], dst[82*456+86])
	}
}
