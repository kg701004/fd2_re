package main

import (
	"log"
	"os"
)

// stepShotShopBuyConfirm drives the REAL native shop purchase entry points
// (setupNativeShopRecipients() then stageNativeShopPurchase(), the exact
// functions a player's Enter press calls) once, as early as possible, instead
// of another FD2_SHOT_SHOP_*_STATE hook that only stages a screenshot pose.
// Every existing shop hook stops at "does the frame look right"; none of them
// actually spend gold or write inventory.
//
// 2026-08-16: this was originally implemented inside the shotSetup block
// (gated on g.frame >= g.shotFrame-1), which turned out to be the exact same
// class of bug as the 2026-08-15 FD2_SHOT_DISMISS_DIALOG timing bug (doc58):
// that gate fires one frame before the screenshot itself, so the multi-frame
// native gold-roll animation job (g.nativeShopUIJob, real-time driven via
// stepNativeShopUILifecycle's now.Sub(job.started), not frame-count driven)
// never got more than ~1 frame of runway no matter how high FD2_SHOT_FRAME
// was set -- raising it only delayed *when* the purchase started, not how
// long it had to finish. Moving initiation to fire once, as early as
// g.nativeShopMode=="menu" is true, gives the animation the intervening
// FD2_SHOT_FRAME-worth of real Update()/Draw() ticks (and real wall-clock
// time, which is what the animation actually keys off) to complete, the same
// way a real playthrough would.
func (g *Game) stepShotShopBuyConfirm() {
	if os.Getenv("FD2_SHOT_SHOP_BUY_CONFIRM") == "" || g.debugShopBuyInitiated {
		return
	}
	if g.nativeShopMode != "menu" {
		return
	}
	g.debugShopBuyInitiated = true
	g.dialog = nil
	g.shopSel = 0
	if !g.setupNativeShopRecipients() || len(g.shopRecipients) == 0 {
		log.Printf("FD2_SHOT_SHOP_BUY_CONFIRM: setupNativeShopRecipients failed or no eligible recipient (mode=%q, frame=%d)", g.nativeShopMode, g.frame)
		return
	}
	recipientID := g.shopRecipients[g.shopRecipientSel]
	recipient := g.partyRoster[recipientID]
	good, goodOK := g.nativeShopSelectedGood()
	g.debugShopBuyRecipientID = recipientID
	g.debugShopBuyGoldBefore = g.gold
	g.debugShopBuyInvBefore = append([]int(nil), recipient.InventorySlots...)
	g.debugShopBuyPending = true
	staged := g.stageNativeShopPurchase()
	log.Printf("FD2_SHOT_SHOP_BUY_CONFIRM: frame=%d good=%+v goodOK=%v recipient=%s(id=%d) goldBefore=%d invBefore=%v staged=%v mode=%q",
		g.frame, good, goodOK, recipient.Name, recipientID, g.gold, g.debugShopBuyInvBefore, staged, g.nativeShopMode)
}
