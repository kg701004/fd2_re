package main

import (
	"testing"
	"time"
)

func TestNativeClassUILifecycleRequiresDrawAcknowledgment(t *testing.T) {
	g := &Game{nativeClassUIJob: &nativeClassUIJob{
		frames: [][]byte{{0}, {1}, {2}, {3}, {4}, {5}},
	}}
	g.stepNativeClassUILifecycle(time.Time{})
	g.stepNativeClassUILifecycle(time.Time{})
	if g.nativeClassUIJob.frame != 0 {
		t.Fatalf("undrawn opening frame advanced to %d", g.nativeClassUIJob.frame)
	}
	for want := 0; want < 6; want++ {
		job := g.nativeClassUIJob
		if job == nil || job.frame != want {
			t.Fatalf("present %d has job %#v", want, job)
		}
		job.drawn = true
		g.stepNativeClassUILifecycle(time.Time{})
	}
	if g.nativeClassUIJob != nil {
		t.Fatal("six-frame list opening did not settle")
	}
}

func TestNativeClassUIClosingDefersContinuationUntilFourthPresent(t *testing.T) {
	completed := false
	g := &Game{nativeClassUIJob: &nativeClassUIJob{
		frames: [][]byte{{0}, {1}, {2}, {3}},
		after:  func() { completed = true },
	}}
	for want := 0; want < 4; want++ {
		if completed || g.nativeClassUIJob.frame != want {
			t.Fatalf("before present %d: completed=%v job=%#v", want, completed, g.nativeClassUIJob)
		}
		g.nativeClassUIJob.drawn = true
		g.stepNativeClassUILifecycle(time.Time{})
	}
	if !completed || g.nativeClassUIJob != nil {
		t.Fatalf("closing completion=%v job=%#v", completed, g.nativeClassUIJob)
	}
}

func TestNativeClassUIPulseUsesTwoBIOSTickCadenceAndWrap(t *testing.T) {
	g := &Game{}
	check := func(tick, want int) {
		t.Helper()
		g.stepNativeClassUIPulseTick(tick)
		if g.nativeClassUIPulse != want {
			t.Fatalf("tick %#x pulse=%d want %d", tick, g.nativeClassUIPulse, want)
		}
	}
	check(0x7ffd, 0)
	check(0x7ffe, 0)
	check(0x7fff, 1)
	check(-0x8000, 1)
	check(-0x7fff, 2)
	check(-0x7ffd, 3)
	check(-0x7ffb, 0)
}
