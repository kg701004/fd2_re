package main

import (
	"fmt"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

// TestSweepNativeAIWinnersAcrossAllChapters is a regression guard for the
// #103/#104 spell/item AI investigation (2026-08-16): does the native
// three-score pipeline (nativeAIThreeScorePlan) ever actually pick
// NativeAICommandSpell/Item in real chapter data? It drives the exact
// production wiring (loadGame + resetBattle, the same call chain
// FD2_CAMP_PREP_BATTLE uses) directly, bypassing the screenshot harness's
// frame-timing limitations (shotSetup only fires near the capture frame,
// leaving no time for more than one AI unit's turn to resolve).
//
// First run (all 30 chapters, turn-1 initial enemies only, right after the
// runtime_append_groups rollout in 58-remake-live-verification-log.md):
// physical=37 spell=19 item=10 none=1081, spread across 8 chapters for
// spell winners (ch06/08/15/19/21/25/30) and 3 for item winners
// (ch27/28/29). Before that rollout every non-rag chapter's units failed
// closed with "lacks raw provenance" before scoring could run at all, so
// spell=0/item=0 here would silently mean either "genuinely no caster
// present" or "provenance broken again" -- the assertions below only rule
// out the latter across the whole campaign, not per chapter.
//
// Second pass (same day) also executes each winner through the real
// production dispatchers (executeNativeCommandTarget / ApplyNativeAIItemCommand,
// same calls aiStep's act() makes) instead of only reading the decision.
// Result: item execution mostly works (10/11), but EVERY spell execution
// failed ("confirmed unit is not a native command candidate" or "native
// command target executor unavailable"). Root cause: executeNativeCommandTarget's
// spell path re-derives its own legal-target list via NativeCommandTargets
// (the same selectionMode/targetCode geometry the ORIGINAL player-facing menu
// uses) and rejects the AI's chosen target if it isn't in that independently
// computed list -- and ScoreNativeAI1598A's own candidate geometry doesn't
// reliably agree with it. This is not a new regression: doc11-enemy-ai.md's
// own table already flagged "法術評分...尚未完整接入重製執行期" (spell scoring
// closed several branches but was never fully wired into remake execution)
// before this test existed -- this sweep is the first empirical measurement
// of that gap (0/19), not the discovery of it. Left as t.Logf, not t.Error:
// failing the whole suite on an already-tracked, not-yet-scoped feature gap
// would just make `go test ./...` permanently red for something that isn't a
// regression. Revisit as a dedicated task, not a quick patch here -- doc11
// separately called the underlying effect chain "量級遠大於評分本身的獨立
// 效果系統" (an independent system far larger than the scoring pass itself).
func TestSweepNativeAIWinnersAcrossAllChapters(t *testing.T) {
	mapForChapter := []int{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29}
	totalPhysical, totalSpell, totalItem, totalNone := 0, 0, 0, 0
	totalSpellExecOK, totalSpellExecFail, totalItemExecOK, totalItemExecFail := 0, 0, 0, 0
	for chapter := 1; chapter <= 30; chapter++ {
		mapN := mapForChapter[chapter-1]
		unitsPath := fmt.Sprintf("assets/maps/map%d/map%d_units.json", mapN, mapN)
		scnPath := fmt.Sprintf("assets/scenarios/ch%02d.json", chapter)

		g := loadGame()
		g.resetBattle(unitsPath, scnPath)
		if g.loadErr != "" {
			t.Logf("ch%02d: loadErr=%s (skipped)", chapter, g.loadErr)
			continue
		}
		if g.st == nil {
			t.Logf("ch%02d: nil state (skipped)", chapter)
			continue
		}
		physical, spell, item, none := 0, 0, 0, 0
		spellExecOK, spellExecFail, itemExecOK, itemExecFail := 0, 0, 0, 0
		for i := 0; i < 300; i++ {
			plan := g.st.NextAIPlan()
			if plan == nil {
				break
			}
			switch {
			case plan.ItemID >= 0:
				item++
				applied, nextRNG, err := g.st.ApplyNativeAIItemCommand(
					plan.U, plan.Target, plan.ItemID, plan.ItemSlot, g.st.NativeItemEffectRows, g.nativeRNGState,
				)
				if err == nil && applied {
					g.nativeRNGState = nextRNG
					itemExecOK++
				} else {
					itemExecFail++
				}
				t.Logf("ch%02d ITEM WINNER: unit=%s(%d,%d) itemID=%d itemSlot=%d target=%s native=%v EXEC applied=%v err=%v",
					chapter, plan.U.ClsName, plan.U.X, plan.U.Y, plan.ItemID, plan.ItemSlot, describeTarget(plan.Target), plan.NativeSourced, applied, err)
			case plan.SpellID >= 0:
				spell++
				message, _, err := g.executeNativeCommandTarget(plan.U, plan.Target, plan.SpellID, plan.Destination)
				if err == nil {
					spellExecOK++
				} else {
					spellExecFail++
				}
				t.Logf("ch%02d SPELL WINNER: unit=%s(%d,%d) spellID=%d target=%s native=%v EXEC msg=%q err=%v",
					chapter, plan.U.ClsName, plan.U.X, plan.U.Y, plan.SpellID, describeTarget(plan.Target), plan.NativeSourced, message, err)
			case plan.Target != nil:
				physical++
			default:
				none++
			}
			if plan.U != nil {
				plan.U.Acted = true
			}
		}
		t.Logf("ch%02d tally: physical=%d spell=%d(exec_ok=%d exec_fail=%d) item=%d(exec_ok=%d exec_fail=%d) none=%d",
			chapter, physical, spell, spellExecOK, spellExecFail, item, itemExecOK, itemExecFail, none)
		totalPhysical += physical
		totalSpell += spell
		totalItem += item
		totalNone += none
		totalSpellExecOK += spellExecOK
		totalSpellExecFail += spellExecFail
		totalItemExecOK += itemExecOK
		totalItemExecFail += itemExecFail
	}
	t.Logf("GRAND TOTAL across all 30 chapters (turn-1 initial enemies only): physical=%d spell=%d(exec_ok=%d exec_fail=%d) item=%d(exec_ok=%d exec_fail=%d) none=%d",
		totalPhysical, totalSpell, totalSpellExecOK, totalSpellExecFail, totalItem, totalItemExecOK, totalItemExecFail, totalNone)
	if totalPhysical == 0 {
		t.Error("zero physical AI winners across the whole campaign -- native AI provenance is likely broken again")
	}
	if totalSpell == 0 {
		t.Error("zero spell AI winners across the whole campaign -- regression in native spell scoring or provenance")
	}
	if totalItem == 0 {
		t.Error("zero item AI winners across the whole campaign -- regression in native item scoring or provenance")
	}
	// Execution success is deliberately NOT asserted here: as of 2026-08-16
	// spell execution is a known, doc11-tracked incomplete feature (0/19
	// succeed), not a regression signal. If it ever reaches 0/0 (no attempts
	// logged at all) that's still caught by the totalSpell==0 check above.
	if totalItemExecOK == 0 && totalItem > 0 {
		t.Error("item AI winners exist but zero executed cleanly -- regression in ApplyNativeAIItemCommand wiring")
	}
}

func describeTarget(u *battle.Unit) string {
	if u == nil {
		return "無"
	}
	return fmt.Sprintf("%s(%d,%d)", u.ClsName, u.X, u.Y)
}
