package battle

import "testing"

// TestResult exercises the win/lose determination directly. It had zero
// test coverage anywhere in this package before 2026-08-15 -- caught while
// live-verifying task #67's ch01 battle loop via a headless multi-turn
// autoplay run: after 45000 simulated frames the game correctly never
// reported a win (real enemies were still alive), which is consistent with
// this function, but that run never actually exercised the true branch
// (fully clearing a 24x24 map with ~20 scattered enemies costs far more
// compute than is proportionate to this check). These tests give direct,
// cheap coverage of the same logic instead.
func TestResult(t *testing.T) {
	t.Run("protect unit dead loses regardless of enemy state", func(t *testing.T) {
		st := newTestState()
		protect := mkUnit(Own, 0, 0, 0, 0)
		protect.Name = "索爾"
		enemy := mkUnit(Enemy, 1, 0, 50, 0)
		st.Units = []*Unit{protect, enemy}
		if got := st.Result("索爾"); got != "lose" {
			t.Fatalf("Result = %q, want \"lose\"", got)
		}
	})

	t.Run("protect unit alive with enemies remaining is undecided", func(t *testing.T) {
		st := newTestState()
		protect := mkUnit(Own, 0, 0, 50, 0)
		protect.Name = "索爾"
		enemy := mkUnit(Enemy, 1, 0, 50, 0)
		st.Units = []*Unit{protect, enemy}
		if got := st.Result("索爾"); got != "" {
			t.Fatalf("Result = %q, want \"\"", got)
		}
	})

	t.Run("all enemies dead with none pending wins", func(t *testing.T) {
		st := newTestState()
		protect := mkUnit(Own, 0, 0, 50, 0)
		protect.Name = "索爾"
		deadEnemy := mkUnit(Enemy, 1, 0, 0, 0)
		st.Units = []*Unit{protect, deadEnemy}
		if got := st.Result("索爾"); got != "win" {
			t.Fatalf("Result = %q, want \"win\"", got)
		}
	})

	t.Run("pending reinforcements block a win even with zero alive enemies on field", func(t *testing.T) {
		st := newTestState()
		protect := mkUnit(Own, 0, 0, 50, 0)
		protect.Name = "索爾"
		// The reinforcement lives only in Roster+PendingGroups (the
		// group-triggered reinforcement mechanism), not in st.Units --
		// PendingCount's other loop (any Units entry with OnField=false)
		// would otherwise count it unconditionally regardless of
		// PendingGroups, which is a different, unrelated pending path.
		reinforcement := mkUnit(Enemy, 5, 5, 50, 0)
		reinforcement.OnField = false
		reinforcement.Group = 1
		st.Units = []*Unit{protect}
		st.Roster = []*Unit{reinforcement}
		st.PendingGroups = map[int]bool{1: true}
		if got := st.Result("索爾"); got != "" {
			t.Fatalf("Result = %q, want \"\" (pending reinforcement should block win)", got)
		}
		// Once the reinforcement group actually clears (PendingGroups no
		// longer marks it), the same all-dead-on-field state should win.
		st.PendingGroups = map[int]bool{}
		if got := st.Result("索爾"); got != "win" {
			t.Fatalf("Result = %q, want \"win\" once no group is pending", got)
		}
	})

	t.Run("empty protect name skips the lose check entirely", func(t *testing.T) {
		st := newTestState()
		enemy := mkUnit(Enemy, 1, 0, 50, 0)
		st.Units = []*Unit{enemy}
		if got := st.Result(""); got != "" {
			t.Fatalf("Result = %q, want \"\" (enemy still alive, no protect check)", got)
		}
	})
}
