package main

import (
	"errors"
	"path/filepath"
	"time"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/inpututil"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/dato"
)

type nativeShopUIAssets struct {
	shops      map[int]*campaign.NativeShopAssets
	portraits  map[int]dato.Frame
	itemAssets battle.NativeItemPanelDataAssets
	effectRows []byte
}

func loadNativeShopUIAssets(
	shared *nativeClassUIAssets,
) (*nativeShopUIAssets, error) {
	if shared == nil || shared.units == nil || shared.strings == nil ||
		shared.font == nil || len(shared.dialogue) <= 17 ||
		len(shared.digits) != 10 {
		return nil, errors.New("native shop UI: shared facility assets unavailable")
	}
	fdotherPath := nativeFDOTHERPath()
	if fdotherPath == "" {
		return nil, errors.New("native shop UI: FDOTHER.DAT unavailable")
	}
	base := filepath.Dir(fdotherPath)
	out := &nativeShopUIAssets{
		shops:     make(map[int]*campaign.NativeShopAssets, 3),
		portraits: make(map[int]dato.Frame, 3),
	}
	for variant, resourceID := range map[int]int{1: 12, 3: 29, 5: 63} {
		assets, err := campaign.DecodeNativeShopAssets(fdotherPath, resourceID)
		if err != nil {
			return nil, err
		}
		out.shops[variant] = assets
	}
	for variant, portraitID := range map[int]int{1: 0x80, 3: 0x82, 5: 0x84} {
		frames, err := dato.DecodeResource(
			filepath.Join(base, "DATO.DAT"), portraitID,
		)
		if err != nil || len(frames) == 0 {
			if err != nil {
				return nil, err
			}
			return nil, errors.New("native shop UI: DATO portrait has no frames")
		}
		out.portraits[variant] = frames[0]
	}
	var err error
	out.itemAssets, err = battle.LoadNativeItemPanelDataAssets(
		fdotherPath, filepath.Join(base, "FDTXT.DAT"),
	)
	if err != nil {
		return nil, err
	}
	out.effectRows, err = battle.LoadNativeItemEffectRowPrefix(
		assetPath("assets/data/native_item_effect_rows.json"),
	)
	if err != nil {
		return nil, err
	}
	return out, nil
}

func (g *Game) setupNativeShop() bool {
	n := g.camp.Node()
	if n == nil || n.Type != "shop" || n.NativeHubVariant == 0 ||
		g.nativeShopUI == nil {
		return false
	}
	if _, ok := g.nativeShopUI.shops[n.NativeHubVariant]; !ok {
		return false
	}
	if _, ok := g.nativeShopUI.portraits[n.NativeHubVariant]; !ok {
		return false
	}
	g.nativeShopVariant = n.NativeHubVariant
	g.nativeShopMode = "menu"
	g.nativeShopServiceSel = 0
	g.nativeShopItemStart = 0
	g.nativeShopConfirmSel = 0
	g.shopSel = 0
	g.resetNativeShopUIPulse()
	return g.beginNativeShopServiceOpening()
}

func (g *Game) nativeShopState() (
	*campaign.NativeShopAssets, dato.Frame, int, bool,
) {
	if g.nativeShopUI == nil || g.nativeClassUI == nil ||
		g.nativeShopVariant != 1 && g.nativeShopVariant != 3 &&
			g.nativeShopVariant != 5 {
		return nil, dato.Frame{}, 0, false
	}
	assets, assetsOK := g.nativeShopUI.shops[g.nativeShopVariant]
	portrait, portraitOK := g.nativeShopUI.portraits[g.nativeShopVariant]
	portraitID := map[int]int{1: 0x80, 3: 0x82, 5: 0x84}[g.nativeShopVariant]
	return assets, portrait, portraitID, assetsOK && portraitOK
}

func (g *Game) composeNativeShopStable() ([]byte, bool) {
	assets, portrait, portraitID, ok := g.nativeShopState()
	if !ok {
		return nil, false
	}
	textIndex := 440
	if g.nativeShopVariant == 1 {
		textIndex = 501
	}
	shared := g.nativeClassUI
	frame, err := campaign.ComposeNativeShopScene(
		assets, shared.dialogue, shared.digits, portrait, portraitID,
		shared.strings, shared.font, g.gold, textIndex,
	)
	return frame, err == nil
}

func (g *Game) composeNativeShopServiceMenu() ([]byte, bool) {
	assets, _, _, ok := g.nativeShopState()
	stable, stableOK := g.composeNativeShopStable()
	if !ok || !stableOK || g.nativeShopMode != "menu" ||
		g.nativeShopServiceSel < 0 || g.nativeShopServiceSel > 3 {
		return nil, false
	}
	frame, err := campaign.ComposeNativeShopServiceSteadyFrame(
		stable, assets, g.nativeShopServiceSel, g.nativeShopUIPulse/2,
	)
	return frame, err == nil
}

func (g *Game) composeNativeShopPurchaseList() ([]byte, bool) {
	if g.nativeShopMode != "purchase" || g.camp == nil {
		return nil, false
	}
	assets, _, _, ok := g.nativeShopState()
	stable, stableOK := g.composeNativeShopStable()
	goods := g.camp.ShopGoods()
	if !ok || !stableOK || len(goods) == 0 ||
		g.shopSel < 0 || g.shopSel >= len(goods) {
		return nil, false
	}
	start, visible := campaign.NativeTwoColumnWindow(
		len(goods), g.shopSel, g.nativeShopItemStart,
	)
	if visible == 0 {
		return nil, false
	}
	g.nativeShopItemStart = start
	itemIDs := make([]int, len(goods))
	for i, good := range goods {
		itemIDs[i] = good.ID
	}
	frame, err := campaign.ComposeNativeShopItemListFrame(
		stable, assets, g.nativeShopUI.itemAssets,
		itemIDs, start, g.shopSel, g.nativeShopUI.effectRows,
		battle.NativeFacilityFullPrice,
	)
	return frame, err == nil
}

func (g *Game) nativeShopSelectedGood() (campaign.Good, bool) {
	if g.camp == nil {
		return campaign.Good{}, false
	}
	goods := g.camp.ShopGoods()
	if g.shopSel < 0 || g.shopSel >= len(goods) {
		return campaign.Good{}, false
	}
	return goods[g.shopSel], true
}

func (g *Game) composeNativeShopPurchaseQuestion() ([]byte, bool) {
	good, goodOK := g.nativeShopSelectedGood()
	_, portrait, portraitID, stateOK := g.nativeShopState()
	stable, stableOK := g.composeNativeShopStable()
	if !goodOK || !stateOK || !stableOK {
		return nil, false
	}
	shared := g.nativeClassUI
	frame, err := campaign.ComposeNativeShopPurchaseMessage(
		stable, shared.dialogue, portrait, portraitID,
		shared.strings, shared.font, campaign.NativeShopPurchaseQuestion,
		g.nativeShopVariant, good.ID, good.Price,
	)
	return frame, err == nil
}

func (g *Game) composeNativeShopPurchaseConfirmation() ([]byte, bool) {
	if g.nativeShopMode != "confirm" ||
		g.nativeShopConfirmSel < 0 || g.nativeShopConfirmSel > 1 {
		return nil, false
	}
	question, ok := g.composeNativeShopPurchaseQuestion()
	if !ok {
		return nil, false
	}
	frame, err := campaign.ComposeNativeConfirmationChoices(
		question, g.nativeClassUI.choices,
		g.nativeShopConfirmSel, g.nativeShopUIPulse/2,
	)
	return frame, err == nil
}

func (g *Game) nativeShopPostChoiceCloseFrame() ([]byte, bool) {
	question, ok := g.composeNativeShopPurchaseQuestion()
	if !ok {
		return nil, false
	}
	frames, err := campaign.NativeClassConfirmationClosingFrames(
		question, g.nativeClassUI.choices,
	)
	if err != nil || len(frames) != 4 {
		return nil, false
	}
	return frames[len(frames)-1], true
}

func (g *Game) composeNativeShopInsufficientGold() ([]byte, bool) {
	if g.nativeShopMode != "insufficient" {
		return nil, false
	}
	postChoiceClose, ok := g.nativeShopPostChoiceCloseFrame()
	if !ok {
		return nil, false
	}
	frame, err := campaign.ComposeNativeShopPurchaseInsufficientGold(
		postChoiceClose, g.nativeClassUI.strings, g.nativeClassUI.font,
		g.nativeShopVariant,
	)
	return frame, err == nil
}

func (g *Game) beginNativeShopServiceOpening() bool {
	assets, _, _, ok := g.nativeShopState()
	stable, stableOK := g.composeNativeShopStable()
	if !ok || !stableOK {
		return false
	}
	frames := make([][]byte, 4)
	for step := range frames {
		var err error
		frames[step], err = campaign.ComposeNativeShopServiceOpeningFrame(
			stable, assets, step,
		)
		if err != nil {
			return false
		}
	}
	g.resetNativeShopUIPulse()
	g.nativeShopUIJob = &nativeClassUIJob{frames: frames}
	return true
}

func (g *Game) beginNativeShopServiceClosing(after func()) bool {
	assets, _, _, ok := g.nativeShopState()
	stable, stableOK := g.composeNativeShopStable()
	if !ok || !stableOK {
		return false
	}
	frames := make([][]byte, 4)
	for step := range frames {
		var err error
		frames[step], err = campaign.ComposeNativeShopServiceClosingFrame(
			stable, assets, step,
		)
		if err != nil {
			return false
		}
	}
	g.nativeShopUIJob = &nativeClassUIJob{
		frames: frames, restore: stable, after: after,
	}
	return true
}

func (g *Game) beginNativeShopPurchaseOpening() bool {
	final, ok := g.composeNativeShopPurchaseList()
	if !ok {
		return false
	}
	stable, ok := g.composeNativeShopStable()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassListOpeningFrames(stable, final)
	if err != nil || len(frames) != 6 {
		return false
	}
	g.nativeShopUIJob = &nativeClassUIJob{frames: frames}
	return true
}

func (g *Game) beginNativeShopPurchaseClosing(after func()) bool {
	final, ok := g.composeNativeShopPurchaseList()
	if !ok {
		return false
	}
	stable, ok := g.composeNativeShopStable()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassListClosingFrames(stable, final)
	if err != nil || len(frames) != 5 {
		return false
	}
	g.nativeShopUIJob = &nativeClassUIJob{
		frames: frames, restore: stable, after: after,
	}
	return true
}

func (g *Game) beginNativeShopConfirmationOpening() bool {
	question, ok := g.composeNativeShopPurchaseQuestion()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassConfirmationOpeningFrames(
		question, g.nativeClassUI.choices,
	)
	if err != nil || len(frames) != 4 {
		return false
	}
	g.resetNativeShopUIPulse()
	g.nativeShopUIJob = &nativeClassUIJob{frames: frames}
	return true
}

func (g *Game) beginNativeShopConfirmationChoiceClosing(after func()) bool {
	question, ok := g.composeNativeShopPurchaseQuestion()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassConfirmationClosingFrames(
		question, g.nativeClassUI.choices,
	)
	if err != nil || len(frames) != 4 {
		return false
	}
	g.nativeShopUIJob = &nativeClassUIJob{frames: frames, after: after}
	return true
}

func (g *Game) beginNativeShopDialogueClosing(
	composed []byte,
	after func(),
) bool {
	stable, ok := g.composeNativeShopStable()
	if !ok || len(composed) != 320*200 {
		return false
	}
	frames, err := campaign.NativeClassListClosingFrames(stable, composed)
	if err != nil || len(frames) != 5 {
		return false
	}
	g.nativeShopUIJob = &nativeClassUIJob{
		frames: frames, restore: stable, after: after,
	}
	return true
}

func (g *Game) returnToNativeShopPurchaseList() {
	g.nativeShopMode = "purchase"
	if !g.beginNativeShopPurchaseOpening() {
		g.nativeShopMode = ""
		g.msg = "原版商店商品清單無法還原"
	}
}

func (g *Game) stepNativeShopUILifecycle(now time.Time) {
	if g.nativeShopMode == "equip_panel" {
		g.stepNativeShopEquipPanelLifecycle()
	}
	job := g.nativeShopUIJob
	if job != nil && len(job.timeline) != 0 {
		if job.started.IsZero() {
			job.started = now
		}
		job.elapsed = now.Sub(job.started)
		if job.frame == 1 && job.drawn {
			after := job.after
			g.nativeShopUIJob = nil
			if after != nil {
				after()
			}
		}
		return
	}
	if job != nil && job.drawn {
		job.drawn = false
		if job.frame < len(job.frames) {
			job.frame++
			if job.frame < len(job.frames) || len(job.restore) != 0 {
				return
			}
		}
		if job.frame >= len(job.frames) {
			after := job.after
			g.nativeShopUIJob = nil
			if after != nil {
				after()
			}
		}
	}
	if g.nativeShopUIJob == nil &&
		(g.nativeShopMode == "menu" || g.nativeShopMode == "confirm" ||
			g.nativeShopMode == "equip_confirm" ||
			g.nativeShopMode == "sell_confirm") {
		g.stepNativeShopUIPulseTick(g.nativeShopUIClock.Sample(now))
	}
}

func (g *Game) drawNativeShopUIJob(screen *ebiten.Image) bool {
	job := g.nativeShopUIJob
	if job == nil {
		return false
	}
	if len(job.timeline) != 0 {
		elapsed := job.elapsed
		total := time.Duration(0)
		for _, candidate := range job.timeline {
			total += candidate.duration
		}
		step := job.timeline[len(job.timeline)-1]
		for _, candidate := range job.timeline {
			if elapsed < candidate.duration {
				step = candidate
				break
			}
			elapsed -= candidate.duration
		}
		if job.elapsed >= total {
			job.frame = 1
		}
		g.presentNativeClassFrameWithPalette(screen, step.frame, step.palette)
		job.drawn = true
		return true
	}
	if job.frame < len(job.frames) {
		g.presentNativeClassFrame(screen, job.frames[job.frame])
		job.drawn = true
		return true
	}
	if len(job.restore) == 320*200 {
		g.presentNativeClassFrame(screen, job.restore)
		job.drawn = true
		return true
	}
	return false
}

func (g *Game) drawNativeShop(screen *ebiten.Image) bool {
	if g.nativeShopMode == "" {
		return false
	}
	if g.drawNativeShopUIJob(screen) {
		return true
	}
	var frame []byte
	var ok bool
	switch g.nativeShopMode {
	case "menu":
		frame, ok = g.composeNativeShopServiceMenu()
	case "purchase":
		frame, ok = g.composeNativeShopPurchaseList()
	case "confirm":
		frame, ok = g.composeNativeShopPurchaseConfirmation()
	case "insufficient":
		frame, ok = g.composeNativeShopInsufficientGold()
	case "recipient_consumable", "recipient_equipment":
		frame, ok = g.composeNativeShopRecipient()
	case "recipient_full":
		frame, ok = g.composeNativeShopRecipientFull()
	case "no_recipient":
		frame, ok = g.composeNativeShopNoEligibleRecipient()
	case "equip_confirm":
		frame, ok = g.composeNativeShopEquipConfirmation()
	case "sell_roster":
		frame, ok = g.composeNativeShopSellRoster()
	case "sell_items":
		frame, ok = g.composeNativeShopSellItems()
	case "sell_empty":
		frame, ok = g.composeNativeShopSellEmpty()
	case "sell_confirm":
		frame, ok = g.composeNativeShopSellConfirmation()
	case "equip_roster":
		frame, ok = g.composeNativeShopEquipRoster()
	case "equip_panel":
		frame, ok = g.composeNativeShopStable()
	}
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
	if g.nativeShopMode == "equip_panel" {
		return g.drawNativeItemPanel(screen)
	}
	return true
}

func (g *Game) nativeShopUIBlocksInput() bool {
	return g.nativeShopUIJob != nil
}

func (g *Game) resetNativeShopUIPulse() {
	g.nativeShopUIClock.Reset()
	g.nativeShopUIPulse = 2
	g.nativeShopUILastTick = 0
	g.nativeShopUIHasTick = false
}

func (g *Game) stepNativeShopUIPulseTick(rawTick int) {
	if !g.nativeShopUIHasTick {
		g.nativeShopUILastTick = rawTick
		g.nativeShopUIHasTick = true
		return
	}
	delta := int16(uint16(rawTick) - uint16(g.nativeShopUILastTick))
	if delta < 2 {
		return
	}
	g.nativeShopUILastTick = rawTick
	g.nativeShopUIPulse = (g.nativeShopUIPulse + 1) & 3
}

func (g *Game) handleNativeShopInput(enter bool) bool {
	if g.nativeShopMode == "" {
		return false
	}
	if g.nativeShopUIBlocksInput() {
		return true
	}
	switch g.nativeShopMode {
	case "menu":
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft) {
			g.nativeShopServiceSel = (g.nativeShopServiceSel + 3) % 4
			g.resetNativeShopUIPulse()
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowRight) {
			g.nativeShopServiceSel = (g.nativeShopServiceSel + 1) % 4
			g.resetNativeShopUIPulse()
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			if !g.beginNativeShopServiceClosing(g.leaveShop) {
				g.leaveShop()
			}
			return true
		}
		if enter {
			if g.nativeShopServiceSel > 2 {
				g.msg = "此原版商店服務的 production owner 尚未接線"
				return true
			}
			open := func() {
				if g.nativeShopServiceSel == 0 {
					g.nativeShopMode = "purchase"
					g.shopSel = 0
					g.nativeShopItemStart = 0
					g.beginNativeShopPurchaseOpening()
					return
				}
				if g.nativeShopServiceSel == 1 {
					if !g.setupNativeShopSellRoster() ||
						!g.beginNativeShopSellRosterOpening() {
						g.nativeShopMode = ""
						g.msg = "原版商店 sell roster 無法還原"
					}
					return
				}
				if !g.setupNativeShopEquipRoster() ||
					!g.beginNativeShopEquipRosterOpening() {
					g.nativeShopMode = ""
					g.msg = "原版商店 equip roster 無法還原"
				}
			}
			if !g.beginNativeShopServiceClosing(open) {
				open()
			}
			return true
		}
	case "purchase":
		goods := g.camp.ShopGoods()
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft) && g.shopSel > 0 {
			g.shopSel--
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowRight) &&
			g.shopSel+1 < len(goods) {
			g.shopSel++
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowUp) && g.shopSel >= 2 {
			g.shopSel -= 2
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowDown) &&
			g.shopSel+2 < len(goods) {
			g.shopSel += 2
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			openMenu := func() {
				g.nativeShopMode = "menu"
				g.nativeShopServiceSel = 0
				g.beginNativeShopServiceOpening()
			}
			if !g.beginNativeShopPurchaseClosing(openMenu) {
				openMenu()
			}
			return true
		}
		if enter && len(goods) != 0 {
			openConfirm := func() {
				g.nativeShopMode = "confirm"
				g.nativeShopConfirmSel = 0
				if !g.beginNativeShopConfirmationOpening() {
					g.nativeShopMode = ""
					g.msg = "原版購買確認視窗無法還原"
				}
			}
			if !g.beginNativeShopPurchaseClosing(openConfirm) {
				openConfirm()
			}
			return true
		}
	case "confirm":
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft) {
			g.nativeShopConfirmSel = campaign.AdvanceNativeClassConfirmation(
				g.nativeShopConfirmSel, -1,
			)
			g.resetNativeShopUIPulse()
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowRight) {
			g.nativeShopConfirmSel = campaign.AdvanceNativeClassConfirmation(
				g.nativeShopConfirmSel, 1,
			)
			g.resetNativeShopUIPulse()
		}
		cancel := inpututil.IsKeyJustPressed(ebiten.KeyEscape) ||
			enter && g.nativeShopConfirmSel == 1
		if cancel {
			closeDialogue := func() {
				postChoiceClose, ok := g.nativeShopPostChoiceCloseFrame()
				if !ok || !g.beginNativeShopDialogueClosing(
					postChoiceClose, g.returnToNativeShopPurchaseList,
				) {
					g.returnToNativeShopPurchaseList()
				}
			}
			if !g.beginNativeShopConfirmationChoiceClosing(closeDialogue) {
				closeDialogue()
			}
			return true
		}
		if enter {
			good, ok := g.nativeShopSelectedGood()
			if !ok {
				return true
			}
			afterChoiceClose := func() {
				if g.gold < good.Price {
					g.nativeShopMode = "insufficient"
					return
				}
				postChoiceClose, frameOK := g.nativeShopPostChoiceCloseFrame()
				openRecipient := func() {
					if !g.setupNativeShopRecipients() {
						g.msg = "原版購買 recipient 缺少 raw 候選資料"
						g.returnToNativeShopPurchaseList()
						return
					}
					if g.nativeShopMode == "no_recipient" {
						if !g.beginNativeShopNoEligibleRecipientOpening() {
							g.msg = "原版購買無合適角色訊息無法還原"
							g.returnToNativeShopPurchaseList()
						}
						return
					}
					if !g.beginNativeShopRecipientOpening() {
						g.msg = "原版購買 recipient 面板無法還原"
						g.returnToNativeShopPurchaseList()
					}
				}
				if !frameOK || !g.beginNativeShopDialogueClosing(
					postChoiceClose, openRecipient,
				) {
					openRecipient()
				}
			}
			if !g.beginNativeShopConfirmationChoiceClosing(afterChoiceClose) {
				afterChoiceClose()
			}
			return true
		}
	case "insufficient":
		if enter || inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			frame, ok := g.composeNativeShopInsufficientGold()
			if !ok || !g.beginNativeShopDialogueClosing(
				frame, g.returnToNativeShopPurchaseList,
			) {
				g.returnToNativeShopPurchaseList()
			}
			return true
		}
	case "recipient_consumable", "recipient_equipment":
		count := len(g.shopRecipients)
		if g.nativeShopMode == "recipient_consumable" {
			delta := 0
			switch {
			case inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft):
				delta = -1
			case inpututil.IsKeyJustPressed(ebiten.KeyArrowRight):
				delta = 1
			case inpututil.IsKeyJustPressed(ebiten.KeyArrowUp):
				delta = -2
			case inpututil.IsKeyJustPressed(ebiten.KeyArrowDown):
				delta = 2
			}
			if delta != 0 {
				g.shopRecipientSel = campaign.AdvanceNativeTwoColumnSelection(
					g.shopRecipientSel, count, delta,
				)
				g.nativeShopRecipientStart, _ = campaign.NativeTwoColumnWindow(
					count, g.shopRecipientSel, g.nativeShopRecipientStart,
				)
			}
		} else {
			if inpututil.IsKeyJustPressed(ebiten.KeyArrowUp) &&
				g.shopRecipientSel > 0 {
				g.shopRecipientSel--
			}
			if inpututil.IsKeyJustPressed(ebiten.KeyArrowDown) &&
				g.shopRecipientSel+1 < count {
				g.shopRecipientSel++
			}
			g.nativeShopRecipientStart, _ = campaign.NativeThreeRowWindow(
				count, g.shopRecipientSel, g.nativeShopRecipientStart,
			)
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			if !g.beginNativeShopRecipientClosing(
				g.returnToNativeShopPurchaseList,
			) {
				g.returnToNativeShopPurchaseList()
			}
			return true
		}
		if enter && count != 0 {
			unit := g.partyRoster[g.shopRecipients[g.shopRecipientSel]]
			if nativeShopInventoryFull(unit) {
				openFull := func() {
					g.nativeShopMode = "recipient_full"
					if !g.beginNativeShopRecipientFullOpening() {
						g.msg = "原版購買滿欄訊息無法還原"
						g.returnToNativeShopPurchaseList()
					}
				}
				if !g.beginNativeShopRecipientClosing(openFull) {
					openFull()
				}
				return true
			}
			beginTransaction := func() {
				if !g.stageNativeShopPurchase() {
					g.nativeShopHasPendingUnit = false
					g.nativeShopPendingUnit = battle.Unit{}
					g.msg = "原版購買交易缺少 raw 資料"
					g.returnToNativeShopPurchaseList()
				}
			}
			if !g.beginNativeShopRecipientClosing(beginTransaction) {
				beginTransaction()
			}
			return true
		}
	case "recipient_full":
		if enter || inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			if !g.beginNativeShopRecipientFullClosing(
				g.returnToNativeShopPurchaseList,
			) {
				g.returnToNativeShopPurchaseList()
			}
			return true
		}
	case "no_recipient":
		if enter || inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			if !g.beginNativeShopNoEligibleRecipientClosing(
				g.returnToNativeShopPurchaseList,
			) {
				g.returnToNativeShopPurchaseList()
			}
			return true
		}
	case "equip_confirm":
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft) {
			g.nativeShopEquipSel = campaign.AdvanceNativeClassConfirmation(
				g.nativeShopEquipSel, -1,
			)
			g.resetNativeShopUIPulse()
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowRight) {
			g.nativeShopEquipSel = campaign.AdvanceNativeClassConfirmation(
				g.nativeShopEquipSel, 1,
			)
			g.resetNativeShopUIPulse()
		}
		cancel := inpututil.IsKeyJustPressed(ebiten.KeyEscape) ||
			enter && g.nativeShopEquipSel == 1
		if cancel || enter {
			if enter && !cancel {
				staged := cloneNativeShopUnit(g.nativeShopPendingUnit)
				if err := campaign.EquipItem(
					&staged, g.shopEquipSlot, g.shopItemStats,
				); err != nil {
					g.nativeShopHasPendingUnit = false
					g.nativeShopPendingUnit = battle.Unit{}
					g.msg = err.Error()
					if !g.beginNativeShopEquipConfirmationClosing(
						g.returnToNativeShopPurchaseList,
					) {
						g.returnToNativeShopPurchaseList()
					}
					return true
				}
				g.nativeShopPendingUnit = staged
			}
			afterPrompt := func() {
				if !g.beginNativeShopPurchaseSuccess() {
					g.nativeShopHasPendingUnit = false
					g.nativeShopPendingUnit = battle.Unit{}
					g.msg = "原版購買成功演出無法還原"
					g.returnToNativeShopPurchaseList()
				}
			}
			if !g.beginNativeShopEquipConfirmationClosing(afterPrompt) {
				afterPrompt()
			}
			return true
		}
	case "sell_roster":
		count := len(g.partyJoinOrder)
		delta := 0
		switch {
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft):
			delta = -1
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowRight):
			delta = 1
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowUp):
			delta = -2
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowDown):
			delta = 2
		}
		if delta != 0 {
			g.shopSellUnitSel = campaign.AdvanceNativeTwoColumnSelection(
				g.shopSellUnitSel, count, delta,
			)
			g.nativeShopSellRosterTop, _ = campaign.NativeTwoColumnWindow(
				count, g.shopSellUnitSel, g.nativeShopSellRosterTop,
			)
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			openMenu := func() {
				g.nativeShopMode = "menu"
				g.nativeShopServiceSel = 1
				g.beginNativeShopServiceOpening()
			}
			if !g.beginNativeShopSellRosterClosing(openMenu) {
				openMenu()
			}
			return true
		}
		if enter && count != 0 {
			_, unit, ok := g.nativeShopSellUnit()
			items, rawOK := nativeShopActiveItemIDs(unit)
			if !ok || !rawOK {
				g.msg = "原版 sell inventory 缺少 raw 資料"
				return true
			}
			openChild := func() {
				if len(items) == 0 {
					g.nativeShopMode = "sell_empty"
					if !g.beginNativeShopSellEmptyOpening() {
						g.msg = "原版 sell empty 訊息無法還原"
						g.setupNativeShopSellRoster()
					}
					return
				}
				if !g.setupNativeShopSellItems() ||
					!g.beginNativeShopSellItemsOpening() {
					g.msg = "原版 sell item list 無法還原"
					g.setupNativeShopSellRoster()
				}
			}
			if !g.beginNativeShopSellRosterClosing(openChild) {
				openChild()
			}
			return true
		}
	case "sell_empty":
		if enter || inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			returnRoster := func() {
				g.returnToNativeShopSellRoster()
			}
			if !g.beginNativeShopSellEmptyClosing(returnRoster) {
				returnRoster()
			}
			return true
		}
	case "sell_items":
		count := len(g.nativeShopSellItemIDs)
		delta := 0
		switch {
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft):
			delta = -1
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowRight):
			delta = 1
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowUp):
			delta = -2
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowDown):
			delta = 2
		}
		if delta != 0 {
			g.shopSellSlotSel = campaign.AdvanceNativeTwoColumnSelection(
				g.shopSellSlotSel, count, delta,
			)
			g.nativeShopSellItemTop, _ = campaign.NativeTwoColumnWindow(
				count, g.shopSellSlotSel, g.nativeShopSellItemTop,
			)
		}
		returnRoster := func() {
			g.returnToNativeShopSellRoster()
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			if !g.beginNativeShopSellItemsClosing(returnRoster) {
				returnRoster()
			}
			return true
		}
		if enter && count != 0 {
			openConfirm := func() {
				g.nativeShopMode = "sell_confirm"
				g.nativeShopSellConfirmSel = 0
				if !g.beginNativeShopSellConfirmationOpening() {
					g.msg = "原版 sell confirmation 無法還原"
					returnRoster()
				}
			}
			if !g.beginNativeShopSellItemsClosing(openConfirm) {
				openConfirm()
			}
			return true
		}
	case "sell_confirm":
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft) {
			g.nativeShopSellConfirmSel =
				campaign.AdvanceNativeClassConfirmation(
					g.nativeShopSellConfirmSel, -1,
				)
			g.resetNativeShopUIPulse()
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyArrowRight) {
			g.nativeShopSellConfirmSel =
				campaign.AdvanceNativeClassConfirmation(
					g.nativeShopSellConfirmSel, 1,
				)
			g.resetNativeShopUIPulse()
		}
		cancel := inpututil.IsKeyJustPressed(ebiten.KeyEscape) ||
			enter && g.nativeShopSellConfirmSel == 1
		if cancel {
			returnRoster := func() {
				g.returnToNativeShopSellRoster()
			}
			if !g.beginNativeShopSellConfirmationClosing(returnRoster) {
				returnRoster()
			}
			return true
		}
		if enter {
			afterConfirm := func() {
				if !g.beginNativeShopSellSuccess() {
					g.msg = "原版 sell transaction 無法還原"
					g.returnToNativeShopSellRoster()
				}
			}
			if !g.beginNativeShopSellConfirmationClosing(afterConfirm) {
				afterConfirm()
			}
			return true
		}
	case "equip_roster":
		count := len(g.partyJoinOrder)
		delta := 0
		switch {
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft):
			delta = -1
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowRight):
			delta = 1
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowUp):
			delta = -2
		case inpututil.IsKeyJustPressed(ebiten.KeyArrowDown):
			delta = 2
		}
		if delta != 0 {
			g.nativeShopEquipUnitSel = campaign.AdvanceNativeTwoColumnSelection(
				g.nativeShopEquipUnitSel, count, delta,
			)
			g.nativeShopEquipRosterTop, _ = campaign.NativeTwoColumnWindow(
				count, g.nativeShopEquipUnitSel,
				g.nativeShopEquipRosterTop,
			)
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			openMenu := func() {
				g.nativeShopMode = "menu"
				g.nativeShopServiceSel = 2
				g.beginNativeShopServiceOpening()
			}
			if !g.beginNativeShopEquipRosterClosing(openMenu) {
				openMenu()
			}
			return true
		}
		if enter && count != 0 {
			openPanel := func() {
				if !g.openNativeShopEquipPanel() {
					g.nativeShopMode = ""
					g.msg = "原版商店 equip item panel 無法還原"
				}
			}
			if !g.beginNativeShopEquipRosterClosing(openPanel) {
				openPanel()
			}
			return true
		}
	case "equip_panel":
		if g.nativeShopEquipPanelBlocksInput() {
			return true
		}
		if inpututil.IsKeyJustPressed(ebiten.KeyEscape) {
			g.beginNativeShopEquipPanelClose()
			return true
		}
		_, unit, ok := g.nativeShopEquipUnit()
		if !ok {
			return true
		}
		rawSlots := nativeItemRawSlots(&unit)
		if len(rawSlots) != 0 {
			key := 0
			switch {
			case inpututil.IsKeyJustPressed(ebiten.KeyArrowUp):
				key = 72
			case inpututil.IsKeyJustPressed(ebiten.KeyArrowDown):
				key = 80
			case inpututil.IsKeyJustPressed(ebiten.KeyArrowLeft):
				key = 75
			case inpututil.IsKeyJustPressed(ebiten.KeyArrowRight):
				key = 77
			}
			if key != 0 {
				selected, _, err := battle.AdvanceNativeItemSelector(
					g.itemSel, len(rawSlots), key, false, 0,
				)
				if err == nil && selected != g.itemSel {
					g.itemSel = selected
					g.refreshNativeItemPanelMode(&unit, true)
				}
			}
		}
		if enter && !g.applyNativeShopEquipSelection() {
			g.msg = "原版商店 equip transaction 缺少 raw 對映"
		}
		return true
	}
	return true
}
