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
	g.nativeShopUIJob = &nativeChurchUIJob{frames: frames}
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
	g.nativeShopUIJob = &nativeChurchUIJob{
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
	g.nativeShopUIJob = &nativeChurchUIJob{frames: frames}
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
	g.nativeShopUIJob = &nativeChurchUIJob{
		frames: frames, restore: stable, after: after,
	}
	return true
}

func (g *Game) stepNativeShopUILifecycle(now time.Time) {
	job := g.nativeShopUIJob
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
	if g.nativeShopUIJob == nil && g.nativeShopMode == "menu" {
		g.stepNativeShopUIPulseTick(g.nativeShopUIClock.Sample(now))
	}
}

func (g *Game) drawNativeShopUIJob(screen *ebiten.Image) bool {
	job := g.nativeShopUIJob
	if job == nil {
		return false
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
	}
	if !ok {
		return false
	}
	g.presentNativeClassFrame(screen, frame)
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
			if g.nativeShopServiceSel != 0 {
				g.msg = "此原版商店服務的 production owner 尚未接線"
				return true
			}
			open := func() {
				g.nativeShopMode = "purchase"
				g.shopSel = 0
				g.nativeShopItemStart = 0
				g.beginNativeShopPurchaseOpening()
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
			g.msg = "原版購買 confirmation production transition 尚未接線"
			return true
		}
	}
	return true
}
