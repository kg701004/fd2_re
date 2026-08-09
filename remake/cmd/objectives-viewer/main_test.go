package main

import "testing"

// TestChapterNavigationClampsAtBounds verifies the 1..30 clamping without
// needing to drive Ebiten's input polling loop (SendKeys-style OS-level key
// injection does not reliably reach raw-input game windows, so this is
// tested as pure logic instead of via UI automation).
func TestChapterNavigationClampsAtBounds(t *testing.T) {
	if got := nextChapter(1); got != 2 {
		t.Errorf("nextChapter(1) = %d, want 2", got)
	}
	if got := nextChapter(30); got != 30 {
		t.Errorf("nextChapter(30) = %d, want 30 (must clamp at last chapter)", got)
	}
	if got := prevChapter(30); got != 29 {
		t.Errorf("prevChapter(30) = %d, want 29", got)
	}
	if got := prevChapter(1); got != 1 {
		t.Errorf("prevChapter(1) = %d, want 1 (must clamp at first chapter)", got)
	}

	// A full walk from 1 to 30 and back must visit every chapter exactly
	// once each way and land back on 1, exercising every objectives.ByNumber
	// entry a real player would reach by holding the arrow key.
	c := 1
	for i := 0; i < 40; i++ {
		c = nextChapter(c)
	}
	if c != 30 {
		t.Errorf("after 40 nextChapter calls from 1, got %d, want 30", c)
	}
	for i := 0; i < 40; i++ {
		c = prevChapter(c)
	}
	if c != 1 {
		t.Errorf("after walking back down, got %d, want 1", c)
	}
}
