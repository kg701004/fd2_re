// Command objectives-viewer is a standalone, runnable demonstration of the
// level-start "hidden condition" screen described in the remaster roadmap.
//
// It renders internal/objectives' walkthrough-sourced 30-chapter table as a
// full-screen panel: win condition, extra guard targets (beyond the
// universal "索爾死亡" rule), and recruit conditions. Left/Right (or A/D)
// switches chapters, matching how a real "chapter start" screen would be
// entered once per chapter.
//
// This is deliberately NOT wired into cmd/fd2's main campaign loop yet: that
// loop is a large, delicate, native-behavior-replicating state machine, and
// bolting an unreviewed new screen into it under time pressure would risk
// its correctness. This command instead ships a genuinely working, visually
// verifiable vertical slice — data layer (internal/objectives, unit-tested)
// through to on-screen rendering — that cmd/fd2 can call into once a real
// "new chapter starts" hook exists in the campaign flow.
//
// Evidence label shown on screen matches AGENTS.md's evidence-grading rule:
// this table is E3 (authored/walkthrough reference), not a verified native
// ABI decode. See internal/objectives' package doc for the full caveat.
package main

import (
	"fmt"
	"image/color"
	"log"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/ebitenutil"
	"github.com/hajimehoshi/ebiten/v2/inpututil"

	"github.com/wicanr2/fd2_re/remake/internal/objectives"
)

const (
	screenW = 960
	screenH = 640
)

var (
	colBG       = color.RGBA{18, 18, 28, 255}
	colPanel    = color.RGBA{28, 34, 58, 235}
	colBorder   = color.RGBA{90, 110, 170, 255}
	colTitle    = color.RGBA{255, 220, 120, 255}
	colLabel    = color.RGBA{140, 180, 255, 255}
	colText     = color.RGBA{235, 235, 235, 255}
	colWarn     = color.RGBA{255, 120, 120, 255}
	colFootnote = color.RGBA{150, 150, 160, 255}
)

type viewer struct {
	font    *Font
	chapter int // 1-based walkthrough chapter number, 1..30
}

// nextChapter and prevChapter are pure, bounds-checked (1..30) chapter step
// functions, factored out of Update so the navigation logic is unit-testable
// without driving Ebiten's input polling (see main_test.go).
func nextChapter(cur int) int {
	if cur < 30 {
		return cur + 1
	}
	return cur
}

func prevChapter(cur int) int {
	if cur > 1 {
		return cur - 1
	}
	return cur
}

func (v *viewer) Update() error {
	if inpututil.IsKeyJustPressed(ebiten.KeyRight) || inpututil.IsKeyJustPressed(ebiten.KeyD) {
		v.chapter = nextChapter(v.chapter)
	}
	if inpututil.IsKeyJustPressed(ebiten.KeyLeft) || inpututil.IsKeyJustPressed(ebiten.KeyA) {
		v.chapter = prevChapter(v.chapter)
	}
	return nil
}

func (v *viewer) Layout(outsideWidth, outsideHeight int) (int, int) {
	return screenW, screenH
}

func (v *viewer) Draw(screen *ebiten.Image) {
	screen.Fill(colBG)

	c, ok := objectives.ByNumber(v.chapter)
	if !ok {
		ebitenutil.DebugPrint(screen, fmt.Sprintf("chapter %d not found", v.chapter))
		return
	}

	if v.font == nil {
		ebitenutil.DebugPrint(screen,
			"找不到可用的中文字型（CJK font not found）\n"+
				"預期在 C:\\Windows\\Fonts\\msjh.ttc 或 assets/fonts/cjk.ttc\n\n"+
				fmt.Sprintf("chapter=%d title=%s win=%s", c.Number, c.Title, c.WinCondition))
		return
	}

	const margin = 48.0
	panelX, panelY := margin, margin
	panelW, panelH := float64(screenW)-margin*2, float64(screenH)-margin*2
	drawPanel(screen, panelX, panelY, panelW, panelH)

	x := panelX + 40
	y := panelY + 32

	v.font.Draw(screen, fmt.Sprintf("第 %d 章 — %s", c.Number, c.Title), x, y, 1.5, colTitle)
	y += v.font.LineHeight(1.5) + 12

	v.font.Draw(screen, "勝利條件", x, y, 1.0, colLabel)
	y += v.font.LineHeight(1.0)
	v.font.Draw(screen, "  "+c.WinCondition, x, y, 1.1, colText)
	y += v.font.LineHeight(1.1) + 20

	v.font.Draw(screen, "失敗條件", x, y, 1.0, colLabel)
	y += v.font.LineHeight(1.0)
	v.font.Draw(screen, "  "+objectives.FailConditionUniversal+"（全章通用）", x, y, 1.1, colWarn)
	y += v.font.LineHeight(1.1)
	if len(c.GuardTargets) == 0 {
		v.font.Draw(screen, "  （本章無額外護衛目標）", x, y, 1.0, colFootnote)
		y += v.font.LineHeight(1.0)
	} else {
		for _, g := range c.GuardTargets {
			v.font.Draw(screen, "  "+g+" 陣亡", x, y, 1.1, colWarn)
			y += v.font.LineHeight(1.1)
		}
	}
	y += 20

	v.font.Draw(screen, "本章可能加入", x, y, 1.0, colLabel)
	y += v.font.LineHeight(1.0)
	if len(c.Recruits) == 0 {
		v.font.Draw(screen, "  （本章無新角色加入）", x, y, 1.0, colFootnote)
		y += v.font.LineHeight(1.0)
	} else {
		for _, r := range c.Recruits {
			line := "  " + r.Who
			if r.Condition != "" {
				line += "（" + r.Condition + "）"
			}
			v.font.Draw(screen, line, x, y, 1.1, colText)
			y += v.font.LineHeight(1.1)
		}
	}

	// Evidence caveat + navigation hint, pinned to the panel bottom.
	footY := panelY + panelH - v.font.LineHeight(0.8)*2 - 16
	v.font.Draw(screen, "資料來源：玩家攻略整理，非原始執行檔逐位元組驗證結果（證據等級 E3）", x, footY, 0.8, colFootnote)
	footY += v.font.LineHeight(0.8)
	v.font.Draw(screen, "← / → 切換章節　　目前：第 "+fmt.Sprint(v.chapter)+" / 30 章", x, footY, 0.8, colFootnote)
}

func drawPanel(dst *ebiten.Image, x, y, w, h float64) {
	sub := ebiten.NewImage(int(w), int(h))
	sub.Fill(colPanel)
	op := &ebiten.DrawImageOptions{}
	op.GeoM.Translate(x, y)
	dst.DrawImage(sub, op)

	border := ebiten.NewImage(int(w), 2)
	border.Fill(colBorder)
	for _, dy := range []float64{0, h - 2} {
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Translate(x, y+dy)
		dst.DrawImage(border, op)
	}
	borderV := ebiten.NewImage(2, int(h))
	borderV.Fill(colBorder)
	for _, dx := range []float64{0, w - 2} {
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Translate(x+dx, y)
		dst.DrawImage(borderV, op)
	}
}

func main() {
	ebiten.SetWindowSize(screenW, screenH)
	ebiten.SetWindowTitle("炎龍騎士團2 重製 — 關卡目標畫面（demo）")

	v := &viewer{font: loadFont(), chapter: 1}
	if v.font == nil {
		log.Println("警告：找不到可用的中文字型，畫面將只顯示除錯文字")
	}
	if err := ebiten.RunGame(v); err != nil {
		log.Fatal(err)
	}
}
