// objectives_screen.go — 章節目標畫面(重製目標 #5:「每個關卡的隱藏條件可以
// 在關卡初始時看到」)。內容來自 internal/objectives(doc28 攻略整理,證據等級
// E3,非原始執行檔逐位元組驗證)。
//
// 觸發點:beat「loadch」成功套用章節 map/roster/script 後(main.go case
// "loadch"),若該章有 objectives 資料就設 g.objChapter 並阻塞 beat runner
// (campInput 攔截 Enter/Space),直到玩家關閉畫面才 g.beatAdvance() 繼續
// 原本的過場。沒有資料的章節(0、31-33 序章/尾聲)不受影響,直接照原節奏走。
package main

import (
	"fmt"
	"image/color"

	"github.com/hajimehoshi/ebiten/v2"

	"github.com/wicanr2/fd2_re/remake/internal/objectives"
)

var (
	objScreenBG     = color.RGBA{18, 18, 28, 255}
	objScreenPanel  = color.RGBA{28, 34, 58, 235}
	objScreenBorder = color.RGBA{90, 110, 170, 255}
	objScreenTitle  = color.RGBA{255, 220, 120, 255}
	objScreenLabel  = color.RGBA{140, 180, 255, 255}
	objScreenText   = color.RGBA{235, 235, 235, 255}
	objScreenWarn   = color.RGBA{255, 120, 120, 255}
	objScreenFoot   = color.RGBA{150, 150, 160, 255}
)

// drawObjectivesScreen 畫章節目標全螢幕面板(640×400 hi-res 內部畫布)。
// 版面沿用 cmd/objectives-viewer 的獨立驗證版,改用引擎既有 g.font,不重複
// 載入字型。
func (g *Game) drawObjectivesScreen(screen *ebiten.Image) {
	screen.Fill(objScreenBG)

	c, ok := objectives.ByNumber(g.objChapter)
	if !ok { // 理論上不會發生(呼叫端已檢查),fail-closed 留診斷訊息而非顯示錯誤資料
		return
	}
	if g.font == nil {
		return // 同引擎其餘畫面慣例:無字型時安靜略過,不畫殘缺文字
	}

	const margin = 32.0
	panelX, panelY := margin, margin
	panelW, panelH := float64(logicalW)-margin*2, float64(logicalH)-margin*2
	g.drawObjPanel(screen, panelX, panelY, panelW, panelH)

	x := panelX + 24
	y := panelY + 16

	g.font.Draw(screen, fmt.Sprintf("第 %d 章 — %s", c.Number, c.Title), x, y, 1.3, objScreenTitle)
	y += g.font.LineHeight(1.3) + 8

	g.font.Draw(screen, "勝利條件", x, y, 0.9, objScreenLabel)
	y += g.font.LineHeight(0.9)
	g.font.Draw(screen, "  "+c.WinCondition, x, y, 1.0, objScreenText)
	y += g.font.LineHeight(1.0) + 12

	g.font.Draw(screen, "失敗條件", x, y, 0.9, objScreenLabel)
	y += g.font.LineHeight(0.9)
	g.font.Draw(screen, "  "+objectives.FailConditionUniversal+"(全章通用)", x, y, 1.0, objScreenWarn)
	y += g.font.LineHeight(1.0)
	if len(c.GuardTargets) == 0 {
		g.font.Draw(screen, "  (本章無額外護衛目標)", x, y, 0.9, objScreenFoot)
		y += g.font.LineHeight(0.9)
	} else {
		for _, target := range c.GuardTargets {
			g.font.Draw(screen, "  "+target+" 陣亡", x, y, 1.0, objScreenWarn)
			y += g.font.LineHeight(1.0)
		}
	}
	y += 12

	g.font.Draw(screen, "本章可能加入", x, y, 0.9, objScreenLabel)
	y += g.font.LineHeight(0.9)
	if len(c.Recruits) == 0 {
		g.font.Draw(screen, "  (本章無新角色加入)", x, y, 0.9, objScreenFoot)
		y += g.font.LineHeight(0.9)
	} else {
		for _, r := range c.Recruits {
			line := "  " + r.Who
			if r.Condition != "" {
				line += "(" + r.Condition + ")"
			}
			g.font.Draw(screen, line, x, y, 1.0, objScreenText)
			y += g.font.LineHeight(1.0)
		}
	}

	footY := panelY + panelH - g.font.LineHeight(0.75)*2 - 10
	g.font.Draw(screen, "資料來源:玩家攻略整理,非原始執行檔逐位元組驗證結果(證據等級 E3)", x, footY, 0.75, objScreenFoot)
	footY += g.font.LineHeight(0.75)
	g.font.Draw(screen, "Enter / Space 繼續", x, footY, 0.75, objScreenFoot)
}

// dismissObjectivesScreen 關閉章節目標畫面,讓 beat runner 繼續原本的過場。抽成
// 獨立 method 是為了不必透過 ebiten 按鍵輪詢就能單元測試(同 cmd/objectives-viewer
// 把 nextChapter/prevChapter 抽成純函式的理由:SendKeys 類 OS 層按鍵不保證能送達
// ebiten raw-input 視窗)。
func (g *Game) dismissObjectivesScreen() {
	g.objChapter = 0
	g.beatAdvance()
}

// drawObjPanel 畫面板背景+邊框。這個畫面顯示期間每幀都會呼叫(擋住 beat runner
// 等玩家按鍵,可能連續畫上百幀),x/y/w/h 每次都是同一組常數(margin 換算),
// 所以背景/邊框圖片 lazy 建一次快取在 Game 上重複貼,不要每幀重新配置 GPU
// 材質(同檔案既有 g.dlgGrad 的作法)。
func (g *Game) drawObjPanel(dst *ebiten.Image, x, y, w, h float64) {
	if g.objPanelBG == nil {
		g.objPanelBG = ebiten.NewImage(int(w), int(h))
		g.objPanelBG.Fill(objScreenPanel)
		g.objPanelBorderH = ebiten.NewImage(int(w), 2)
		g.objPanelBorderH.Fill(objScreenBorder)
		g.objPanelBorderV = ebiten.NewImage(2, int(h))
		g.objPanelBorderV.Fill(objScreenBorder)
	}

	op := &ebiten.DrawImageOptions{}
	op.GeoM.Translate(x, y)
	dst.DrawImage(g.objPanelBG, op)

	for _, dy := range []float64{0, h - 2} {
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Translate(x, y+dy)
		dst.DrawImage(g.objPanelBorderH, op)
	}
	for _, dx := range []float64{0, w - 2} {
		op := &ebiten.DrawImageOptions{}
		op.GeoM.Translate(x+dx, y)
		dst.DrawImage(g.objPanelBorderV, op)
	}
}
