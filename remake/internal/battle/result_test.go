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

	// 2026-08-30: doc28 §2 有 18 章需要「索爾 OR 一或多個額外護衛死亡」都算
	// 敗北(聯集),不是用額外護衛「取代」索爾檢查。下面三個案例直接對應
	// campaign.go Node.Protect/ProtectGuards 的聯集語意與 main.go checkResult
	// 組出的呼叫方式(main.go 恆傳 "索爾" + 額外護衛清單)。
	t.Run("single extra guard dead loses even with sol alive (union, ch12/15/16/19/22/25 shape)", func(t *testing.T) {
		st := newTestState()
		sol := mkUnit(Own, 0, 0, 50, 0)
		sol.Name = "索爾"
		guard := mkUnit(Ally, 1, 1, 0, 0) // 額外護衛已死
		guard.Name = "米亞斯多德"
		enemy := mkUnit(Enemy, 2, 0, 50, 0)
		st.Units = []*Unit{sol, guard, enemy}
		if got := st.Result("索爾", "米亞斯多德"); got != "lose" {
			t.Fatalf("Result = %q, want \"lose\" (extra guard died)", got)
		}
	})

	t.Run("sol dead loses even though every named extra guard is alive (union, not replaced)", func(t *testing.T) {
		st := newTestState()
		sol := mkUnit(Own, 0, 0, 0, 0) // 索爾已死
		sol.Name = "索爾"
		guard := mkUnit(Ally, 1, 1, 50, 0)
		guard.Name = "米亞斯多德"
		enemy := mkUnit(Enemy, 2, 0, 50, 0)
		st.Units = []*Unit{sol, guard, enemy}
		if got := st.Result("索爾", "米亞斯多德"); got != "lose" {
			t.Fatalf("Result = %q, want \"lose\" (Sol dying must still lose even with an extra protect name set -- pre-2026-08-30 bug replaced the Sol check instead of adding to it)", got)
		}
	})

	t.Run("multi-guard chapter (ch10/18/21/23/26 shape): all alive is undecided, any one dying loses", func(t *testing.T) {
		st := newTestState()
		sol := mkUnit(Own, 0, 0, 50, 0)
		sol.Name = "索爾"
		g1 := mkUnit(Ally, 1, 1, 50, 0)
		g1.Name = "約拿"
		g2 := mkUnit(Ally, 2, 1, 50, 0)
		g2.Name = "蘭斯洛特"
		enemy := mkUnit(Enemy, 3, 0, 50, 0)
		st.Units = []*Unit{sol, g1, g2, enemy}
		if got := st.Result("索爾", "約拿", "蘭斯洛特"); got != "" {
			t.Fatalf("Result = %q, want \"\" (all three still alive)", got)
		}
		g2.HP = 0 // 其中一個護衛死亡
		if got := st.Result("索爾", "約拿", "蘭斯洛特"); got != "lose" {
			t.Fatalf("Result = %q, want \"lose\" (one of two extra guards died)", got)
		}
	})

	// 2026-08-30 續輪:ch02(村民全滅)/ch13(精靈族全滅)/ch20(精靈全滅)是陣營
	// 全滅型敗北條件,無法用具名單位表達(mapN_units.json 這些 NPC 全部沒有
	// name),改用 Camp+Portrait 識別群組,見 ProtectGroup 的註解與
	// 91-worklist.md 同日 group-wipe 條目。以下對應 ResultWithGroups。
	t.Run("group wipe: some members alive is undecided even with sol/enemies present", func(t *testing.T) {
		st := newTestState()
		sol := mkUnit(Own, 0, 0, 50, 0)
		sol.Name = "索爾"
		villager1 := mkUnit(Ally, 1, 1, 50, 0)
		villager1.Portrait = 133
		villager2 := mkUnit(Ally, 2, 1, 0, 0) // 已死
		villager2.Portrait = 134
		enemy := mkUnit(Enemy, 3, 0, 50, 0)
		st.Units = []*Unit{sol, villager1, villager2, enemy}
		group := ProtectGroup{Camp: Ally, Portraits: []int{133, 134}}
		if got := st.ResultWithGroups([]string{"索爾"}, []ProtectGroup{group}); got != "" {
			t.Fatalf("ResultWithGroups = %q, want \"\" (villager1 still alive, group not wiped)", got)
		}
	})

	t.Run("group wipe: all members dead loses even with sol and enemies alive", func(t *testing.T) {
		st := newTestState()
		sol := mkUnit(Own, 0, 0, 50, 0)
		sol.Name = "索爾"
		villager1 := mkUnit(Ally, 1, 1, 0, 0)
		villager1.Portrait = 133
		villager2 := mkUnit(Ally, 2, 1, 0, 0)
		villager2.Portrait = 134
		enemy := mkUnit(Enemy, 3, 0, 50, 0)
		st.Units = []*Unit{sol, villager1, villager2, enemy}
		group := ProtectGroup{Camp: Ally, Portraits: []int{133, 134}}
		if got := st.ResultWithGroups([]string{"索爾"}, []ProtectGroup{group}); got != "lose" {
			t.Fatalf("ResultWithGroups = %q, want \"lose\" (all matching villagers dead)", got)
		}
	})

	t.Run("group wipe: no matching units in st.Units never triggers a loss (misconfigured group fails closed)", func(t *testing.T) {
		st := newTestState()
		sol := mkUnit(Own, 0, 0, 50, 0)
		sol.Name = "索爾"
		enemy := mkUnit(Enemy, 3, 0, 50, 0)
		st.Units = []*Unit{sol, enemy}
		group := ProtectGroup{Camp: Ally, Portraits: []int{133, 134}} // 該地圖根本沒有這個群組
		if got := st.ResultWithGroups([]string{"索爾"}, []ProtectGroup{group}); got != "" {
			t.Fatalf("ResultWithGroups = %q, want \"\" (zero matching units must not vacuously count as wiped -- would be an instant loss on any typo'd portrait id)", got)
		}
	})

	t.Run("group wipe: named protect and group checks are a union, either alone can lose", func(t *testing.T) {
		st := newTestState()
		sol := mkUnit(Own, 0, 0, 0, 0) // 索爾已死
		sol.Name = "索爾"
		elf1 := mkUnit(Ally, 1, 1, 50, 0)
		elf1.Portrait = 72
		st.Units = []*Unit{sol, elf1}
		group := ProtectGroup{Camp: Ally, Portraits: []int{72}}
		if got := st.ResultWithGroups([]string{"索爾"}, []ProtectGroup{group}); got != "lose" {
			t.Fatalf("ResultWithGroups = %q, want \"lose\" (sol died even though the elf group is untouched)", got)
		}
	})
}
