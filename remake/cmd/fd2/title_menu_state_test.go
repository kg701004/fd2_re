package main

import "testing"

func TestTitleMenuTraceWrapsAndConfirmsAfterFlash(t *testing.T) {
	var s TitleMenuState
	if s.Step(TitleMenuUp) != TitleMenuNoAction || s.Selection != 2 {
		t.Fatalf("up from zero = selection %d", s.Selection)
	}
	if s.Step(TitleMenuDown) != TitleMenuNoAction || s.Selection != 0 {
		t.Fatalf("down wrap = selection %d", s.Selection)
	}
	s.Step(TitleMenuDown)
	if s.Selection != 1 {
		t.Fatalf("load selection = %d, want 1", s.Selection)
	}
	s.Step(TitleMenuConfirm)
	if s.FlashTicks != 24 {
		t.Fatalf("confirm flash = %d, want 24", s.FlashTicks)
	}
	for i := 0; i < 23; i++ {
		if got := s.Step(TitleMenuTick); got != TitleMenuNoAction {
			t.Fatalf("action fired early at tick %d: %d", i, got)
		}
	}
	if got := s.Step(TitleMenuTick); got != TitleMenuLoadSlots {
		t.Fatalf("final flash action = %d, want load slots", got)
	}
}

func TestTitleMenuThirdSelectionIsNativeContinue(t *testing.T) {
	s := TitleMenuState{Selection: 2}
	s.Step(TitleMenuConfirm)
	for i := 0; i < 23; i++ {
		if got := s.Step(TitleMenuTick); got != TitleMenuNoAction {
			t.Fatalf("action fired early at tick %d: %d", i, got)
		}
	}
	if got := s.Step(TitleMenuTick); got != TitleMenuContinue {
		t.Fatalf("third selection action=%d, want native CONTINUE", got)
	}
}

func TestTitleSlotTraceIsBoundedAndCancelable(t *testing.T) {
	s := TitleSlotState{Selection: 3}
	if got, _, _ := s.Step(TitleSlotDown); got != 3 {
		t.Fatalf("down at last slot wrapped to %d", got)
	}
	for i := 0; i < 3; i++ {
		s.Step(TitleSlotUp)
	}
	if s.Selection != 0 {
		t.Fatalf("up trace selection = %d, want 0", s.Selection)
	}
	if got, confirm, cancel := s.Step(TitleSlotConfirm); got != 0 || !confirm || cancel {
		t.Fatalf("confirm result=(%d,%v,%v)", got, confirm, cancel)
	}
	if got, confirm, cancel := s.Step(TitleSlotCancel); got != 0 || confirm || !cancel {
		t.Fatalf("cancel result=(%d,%v,%v)", got, confirm, cancel)
	}
}
