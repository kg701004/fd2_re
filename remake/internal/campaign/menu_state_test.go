package campaign

import "testing"

func TestMenuStateTraceIsBoundedAndDataDriven(t *testing.T) {
	s := MenuState{Selection: 9, Count: 3}
	if got, confirm := s.Step(MenuTick); got != 2 || confirm {
		t.Fatalf("initial clamp=(%d,%v), want (2,false)", got, confirm)
	}
	s.Step(MenuDown)
	if s.Selection != 2 {
		t.Fatalf("down at last option wrapped to %d", s.Selection)
	}
	s.Step(MenuUp)
	if s.Selection != 1 {
		t.Fatalf("up selection=%d, want 1", s.Selection)
	}
	if got, confirm := s.Step(MenuConfirm); got != 1 || !confirm {
		t.Fatalf("confirm=(%d,%v), want (1,true)", got, confirm)
	}
	s.Count = 0
	if got, confirm := s.Step(MenuConfirm); got != 0 || confirm {
		t.Fatalf("empty menu confirm=(%d,%v)", got, confirm)
	}
}
