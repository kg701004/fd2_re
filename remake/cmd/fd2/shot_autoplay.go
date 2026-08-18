package main

import (
	"fmt"
	"log"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
)

func shotAutoplayDebugf(format string, args ...interface{}) {
	if os.Getenv("FD2_SHOT_AUTOPLAY_DEBUG") != "" {
		log.Printf("[autoplay] "+format, args...)
	}
}

// stepShotAutoplay drives the player's own turn automatically toward the
// nearest enemy each frame, one confirm()-equivalent step at a time, so a
// headless FD2_SHOT session can walk a unit across several real turns into
// weapon range and land a genuine attack -- something no existing FD2_SHOT_*
// hook does (they all stage a single fixed state, not multi-turn play).
// Debug-only, gated behind FD2_SHOT_AUTOPLAY=1; added 2026-08-15 while
// live-verifying task #67's ch01 battle loop (attack execution was the one
// sub-mechanic never actually exercised end-to-end -- see doc58's "待驗證"
// list). It bypasses the ring's cosmetic open/close animation via
// resetActionOverlayLifecycle() (the same shortcut FD2_SHOT_ATKSEL already
// uses) and calls the real finishSelectedWait()/confirm() functions for
// every state-changing step, so the movement/attack/wait logic exercised is
// identical to real play -- only the ring animation and keyboard-driven
// ringSel navigation are skipped.
func (g *Game) stepShotAutoplay() {
	if os.Getenv("FD2_SHOT_AUTOPLAY") == "" || g.st == nil {
		return
	}
	// Dismiss dialog on sight, every frame -- FD2_SHOT_DISMISS_DIALOG only
	// fires once, tied to the SAME frame>=shotFrame-1 gate the screenshot
	// itself fires one frame later on, leaving ~1 frame of runway. Autoplay
	// needs the opening story dialog cleared immediately (frame ~0) so the
	// hundreds/thousands of frames up to FD2_SHOT_FRAME are actually usable
	// for multi-turn walking, not spent blocked behind the dialog box.
	if len(g.dialog) > 0 {
		g.dialog = nil
		g.dlgShown, g.dlgPhase, g.dlgPage, g.dlgScrollT = dlgNone, 0, 0, 0
	}
	if g.result != "" || g.walk != nil || g.atk != nil || g.aiBusy {
		return
	}
	if g.sel == nil {
		var u *battle.Unit
		for _, unit := range g.st.Units {
			if unit != nil && unit.Camp == battle.Own && unit.OnField && unit.Alive() &&
				!unit.Acted && !unit.Paralyzed {
				u = unit
				break
			}
		}
		if u == nil {
			shotAutoplayDebugf("no unacted own unit -> endTurn (turn=%d)", g.st.Turn)
			g.endTurn()
			return
		}
		g.curX, g.curY = u.X, u.Y
		g.confirm() // 選取單位
		g.selOrigX, g.selOrigY = u.X, u.Y
		shotAutoplayDebugf("selected %s at (%d,%d) sel!=nil=%v", u.ClsName, u.X, u.Y, g.sel != nil)
		return
	}
	nearest := g.shotAutoplayNearestEnemy()
	nearestDesc := "無"
	if nearest != nil {
		nearestDesc = fmt.Sprintf("%s(%d,%d)", nearest.ClsName, nearest.X, nearest.Y)
	}
	if !g.moved {
		if nearest != nil && g.st.InAttackRange(g.sel, nearest.X, nearest.Y) {
			g.curX, g.curY = g.sel.X, g.sel.Y
			g.confirm() // 原地不動 → 開指令環
			shotAutoplayDebugf("in range at (%d,%d), open ring in place, moved=%v ring=%v", g.sel.X, g.sel.Y, g.moved, g.ring)
			return
		}
		destX, destY := g.sel.X, g.sel.Y
		if nearest != nil {
			reach := g.st.Reachable(g.sel)
			bestD := shotAutoplayManhattan(g.sel.X, g.sel.Y, nearest.X, nearest.Y)
			for c := range reach {
				if g.st.UnitAt(c.X, c.Y) != nil {
					continue
				}
				if d := shotAutoplayManhattan(c.X, c.Y, nearest.X, nearest.Y); d < bestD {
					bestD, destX, destY = d, c.X, c.Y
				}
			}
			shotAutoplayDebugf("sel=(%d,%d) nearest=%s reachN=%d best=(%d,%d) bestD=%d",
				g.sel.X, g.sel.Y, nearestDesc, len(reach), destX, destY, bestD)
		}
		g.curX, g.curY = destX, destY
		g.confirm() // 原地開環,或沿路徑走向可達格(g.walk 接手,下一幀再進來時 g.walk!=nil 會先跳過)
		shotAutoplayDebugf("confirmed dest=(%d,%d) walk!=nil=%v moved=%v selPos=(%d,%d)",
			destX, destY, g.walk != nil, g.moved, g.sel.X, g.sel.Y)
		return
	}
	// g.moved==true 代表指令環已經(或即將)自動開啟(beginActionOverlayOpen);
	// 用跟 FD2_SHOT_ATKSEL 相同的手法瞬間關環(略過純演出用的開/關動畫),
	// 直接呼叫真正的 confirm()/finishSelectedWait() 執行後續邏輯。
	g.resetActionOverlayLifecycle()
	if nearest != nil && g.st.InAttackRange(g.sel, nearest.X, nearest.Y) {
		g.msg = "攻擊:選擇目標"
		g.curX, g.curY = nearest.X, nearest.Y
		g.confirm() // 攻擊階段:游標在攻擊範圍內的敵 → 真的攻擊
		shotAutoplayDebugf("attacked %s, msg=%q sel!=nil=%v", nearestDesc, g.msg, g.sel != nil)
		return
	}
	shotAutoplayDebugf("no target in range (nearest=%s), finishSelectedWait sel!=nil=%v", nearestDesc, g.sel != nil)
	g.finishSelectedWait()
}

func (g *Game) shotAutoplayNearestEnemy() *battle.Unit {
	if g.sel == nil {
		return nil
	}
	var nearest *battle.Unit
	best := 1 << 30
	for _, unit := range g.st.Units {
		if unit == nil || unit.Camp == battle.Own || !unit.OnField || !unit.Alive() {
			continue
		}
		if d := shotAutoplayManhattan(g.sel.X, g.sel.Y, unit.X, unit.Y); d < best {
			best, nearest = d, unit
		}
	}
	return nearest
}

func shotAutoplayManhattan(ax, ay, bx, by int) int {
	dx, dy := ax-bx, ay-by
	if dx < 0 {
		dx = -dx
	}
	if dy < 0 {
		dy = -dy
	}
	return dx + dy
}
