package main

import (
	"log"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

// stepShotForceResult drives FD2_SHOT_FORCE_WIN / FD2_SHOT_FORCE_LOSE once, as
// early as possible, instead of inside the shotSetup block (gated on
// g.frame >= g.shotFrame-1).
//
// 2026-08-16: originally both hooks lived inside shotSetup, which is the same
// class of bug as the shop-buy-confirm and dismiss-dialog timing bugs already
// documented in doc58: firing one frame before the screenshot itself leaves
// no real runway for whatever g.enterNode() sets up next to settle (a dialog
// box's reveal animation runs over several real Update() ticks via
// g.dlgPhase/g.dlgT, not instantly). Live-testing FD2_SHOT_FORCE_LOSE against
// retreat_ch01 (a plain "story" node with lines but no beats) surfaced this
// directly: the captured screenshot showed an empty dialog box with no
// portrait/text, because the reveal animation had had ~0 real frames to run.
// Moving initiation to fire once, as soon as g.st != nil, gives the
// intervening FD2_SHOT_FRAME-worth of real ticks to the new node's own
// presentation, the same way stepShotShopBuyConfirm's fix worked.
func (g *Game) stepShotForceResult() {
	if g.debugForceResultInitiated {
		return
	}
	forceWin := os.Getenv("FD2_SHOT_FORCE_WIN") != ""
	forceLose := os.Getenv("FD2_SHOT_FORCE_LOSE") != ""
	if (!forceWin && !forceLose) || g.st == nil {
		return
	}
	g.debugForceResultInitiated = true
	g.dialog = nil
	if forceWin {
		killed := 0
		for _, u := range g.st.Units {
			if u != nil && u.Camp == battle.Enemy && u.HP > 0 {
				u.HP = 0
				killed++
			}
		}
		// Killing every enemy already in g.st.Units isn't enough on its own:
		// later-turn reinforcement waves live in g.st.Roster with
		// PendingGroups marked true until their trigger event fires, and
		// PendingCount() correctly still counts them as blocking a win.
		// Debug-only: this hook is about the win->transition wiring, not
		// re-proving the pending-blocks-win logic result_test.go covers.
		pendingCleared := len(g.st.PendingGroups)
		g.st.PendingGroups = map[int]bool{}
		g.checkResult()
		nodeBefore := ""
		if g.camp != nil {
			nodeBefore = g.camp.Cur
		}
		result := g.result
		log.Printf("FD2_SHOT_FORCE_WIN: killed=%d enemies, cleared %d pending group(s), g.result=%q, node before Enter=%q",
			killed, pendingCleared, result, nodeBefore)
		if result != "" && g.camp != nil {
			next := g.camp.Advance(result)
			g.enterNode()
			log.Printf("FD2_SHOT_FORCE_WIN: Advance(%q) -> next node=%q, g.camp.Cur after enterNode()=%q",
				result, next, g.camp.Cur)
		}
		return
	}
	// forceLose: mirrors the win branch for the on_lose side of the
	// transition. checkResult()'s protect-unit-dead branch (battle.State.
	// Result, combat.go) is exercised by zeroing the HP of whichever unit is
	// this node's protect target (node.Protect, default "索爾" -- same lookup
	// checkResult() itself uses).
	protect := "索爾"
	if g.camp != nil {
		if n := g.camp.Node(); n != nil && n.Protect != "" {
			protect = n.Protect
		}
	}
	killed := false
	for _, u := range g.st.Units {
		if u != nil && u.Name == protect && u.HP > 0 {
			u.HP = 0
			killed = true
		}
	}
	g.checkResult()
	nodeBefore := ""
	if g.camp != nil {
		nodeBefore = g.camp.Cur
	}
	result := g.result
	log.Printf("FD2_SHOT_FORCE_LOSE: protect=%q killed=%v g.result=%q, node before Enter=%q",
		protect, killed, result, nodeBefore)
	if result != "" && g.camp != nil {
		next := g.camp.Advance(result)
		g.enterNode()
		log.Printf("FD2_SHOT_FORCE_LOSE: Advance(%q) -> next node=%q, g.camp.Cur after enterNode()=%q",
			result, next, g.camp.Cur)
	}
}
