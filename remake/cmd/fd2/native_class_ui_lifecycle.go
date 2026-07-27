package main

import (
	"time"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

type nativeClassUIJob struct {
	frames [][]byte
	frame  int
	drawn  bool
	after  func()
}

func (g *Game) beginNativeClassListOpening() bool {
	final, ok := g.composeNativeClassListFrame()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassListOpeningFrames(g.nativeClassUI.background, final)
	if err != nil || len(frames) != 6 {
		return false
	}
	g.nativeClassUIJob = &nativeClassUIJob{frames: frames}
	return true
}

func (g *Game) beginNativeClassConfirmationOpening() bool {
	question, ok := g.composeNativeClassConfirmationQuestion()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassConfirmationOpeningFrames(question, g.nativeClassUI.choices)
	if err != nil || len(frames) != 4 {
		return false
	}
	g.resetNativeClassUIPulse()
	g.nativeClassUIJob = &nativeClassUIJob{frames: frames}
	return true
}

func (g *Game) beginNativeClassConfirmationClosing(after func()) bool {
	question, ok := g.composeNativeClassConfirmationQuestion()
	if !ok {
		return false
	}
	frames, err := campaign.NativeClassConfirmationClosingFrames(question, g.nativeClassUI.choices)
	if err != nil || len(frames) != 4 {
		return false
	}
	g.nativeClassUIJob = &nativeClassUIJob{frames: frames, after: after}
	return true
}

// stepNativeClassUILifecycle advances only a frame that Draw acknowledged.
// The continuation runs after the final closing frame has been presented.
func (g *Game) stepNativeClassUILifecycle(now time.Time) {
	job := g.nativeClassUIJob
	if job != nil && job.drawn {
		job.drawn = false
		job.frame++
		if job.frame >= len(job.frames) {
			after := job.after
			g.nativeClassUIJob = nil
			if after != nil {
				after()
			}
		}
	}
	if g.nativeClassUIJob == nil && g.churchMode == "class_confirm" {
		g.stepNativeClassUIPulseTick(g.nativeClassUIClock.Sample(now))
	}
}

func (g *Game) drawNativeClassUIJob(screen *ebiten.Image) bool {
	job := g.nativeClassUIJob
	if job == nil || job.frame < 0 || job.frame >= len(job.frames) {
		return false
	}
	g.presentNativeClassFrame(screen, job.frames[job.frame])
	job.drawn = true
	return true
}

func (g *Game) nativeClassUIBlocksInput() bool {
	return g.nativeClassUIJob != nil
}

func (g *Game) resetNativeClassUIPulse() {
	g.nativeClassUIClock.Reset()
	g.nativeClassUIPulse = 0
	g.nativeClassUILastTick = 0
	g.nativeClassUIHasTick = false
}

// 0x19953 increments its two-bit counter when the signed BIOS low-word delta
// reaches two ticks. The selected choice uses counter/2 as its cell variant.
func (g *Game) stepNativeClassUIPulseTick(rawTick int) {
	if !g.nativeClassUIHasTick {
		g.nativeClassUILastTick = rawTick
		g.nativeClassUIHasTick = true
		return
	}
	delta := int16(uint16(rawTick) - uint16(g.nativeClassUILastTick))
	if delta < 2 {
		return
	}
	g.nativeClassUILastTick = rawTick
	g.nativeClassUIPulse = (g.nativeClassUIPulse + 1) & 3
}

func (g *Game) returnToNativeClassList() {
	g.churchMode = "class"
	g.churchBranches = nil
	g.churchClassID = -1
	g.churchSel = 0
	g.beginNativeClassListOpening()
}
