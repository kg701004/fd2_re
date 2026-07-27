package main

import (
	"bytes"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

func nativeIndexedTransitionSpecForTest() campaign.HandlerIndexedTransition {
	return campaign.HandlerIndexedTransition{
		TileX: 6, TileY: 6, RadialRadius: 10, RadialRadiusStep: 8,
		StartY: 0, EndY: 192, ClipWidth: 312, ClipHeight: 192,
		Frames: 9, FrameDelayMs: 5, TailDelayMs: 500,
		PaletteRangeStart: 0, PaletteRangeEnd: 255,
		PaletteDeltaStart: 0, PaletteDeltaEnd: 62, PaletteDeltaStep: 2,
		PaletteDelayMs: 4,
	}
}

func TestNativeIndexedTransitionRequiresEveryDrawBeforeContinuation(t *testing.T) {
	assets, field, state := completeNativeMapFrameFixture(t)
	for i := range assets.LUTs {
		for p := range assets.LUTs[i] {
			assets.LUTs[i][p] = byte(p)
		}
	}
	actor := *state.Units[0]
	actor.SetMapPlacement(6, 6, 0)
	g := &Game{
		nativeMapAssets: assets, m: field,
		storyActors: []battle.Unit{actor},
	}
	continued := 0
	if err := g.startNativeIndexedTransition(nativeIndexedTransitionSpecForTest(), func() { continued++ }); err != nil {
		t.Fatal(err)
	}
	if g.indexedTransition == nil || g.indexedTransition.frame != 0 {
		t.Fatal("first pass was not atomically precomposed")
	}
	for i := 0; i < 20; i++ {
		g.stepNativeIndexedTransition()
	}
	if g.indexedTransition.frame != 0 || continued != 0 {
		t.Fatal("Update advanced an unacknowledged transition frame")
	}
	for want := 1; want < 9; want++ {
		g.indexedTransition.drawn = true
		g.stepNativeIndexedTransition()
		if g.indexedTransition == nil || g.indexedTransition.frame != want {
			t.Fatalf("pass=%d, want %d", g.indexedTransition.frame, want)
		}
	}
	g.indexedTransition.drawn = true
	g.stepNativeIndexedTransition()
	if g.indexedTransition.phase != nativeTransitionTail || g.indexedTransition.tailTicks != 30 {
		t.Fatalf("tail=%d phase=%d", g.indexedTransition.tailTicks, g.indexedTransition.phase)
	}
	for i := 0; i < 31; i++ {
		g.stepNativeIndexedTransition()
	}
	if g.indexedTransition.phase != nativeTransitionPalette || g.indexedTransition.paletteStep != 0 {
		t.Fatalf("palette did not start after exact tail: phase=%d step=%d", g.indexedTransition.phase, g.indexedTransition.paletteStep)
	}
	pixels := append([]byte(nil), g.indexedTransition.vga...)
	for step := 0; step < 32; step++ {
		if step > 0 && g.indexedTransition.paletteStep != step {
			t.Fatalf("palette step=%d want %d", g.indexedTransition.paletteStep, step)
		}
		g.indexedTransition.drawn = true
		g.stepNativeIndexedTransition()
	}
	if g.indexedTransition != nil || continued != 1 {
		t.Fatalf("completion job=%v continuation=%d", g.indexedTransition, continued)
	}
	if !bytes.Equal(g.nativeMapVGA, pixels) {
		t.Fatal("palette phase changed indexed pixels")
	}
}

func TestNativeIndexedTransitionStartFailsClosedOnMissingRawAssets(t *testing.T) {
	g := &Game{nativeMapWork: []byte{7}, nativeMapVGA: []byte{8}}
	beforeWork, beforeVGA := append([]byte(nil), g.nativeMapWork...), append([]byte(nil), g.nativeMapVGA...)
	if err := g.startNativeIndexedTransition(nativeIndexedTransitionSpecForTest(), nil); err == nil {
		t.Fatal("missing native source was accepted")
	}
	if g.indexedTransition != nil || !bytes.Equal(g.nativeMapWork, beforeWork) || !bytes.Equal(g.nativeMapVGA, beforeVGA) {
		t.Fatal("rejected transition partially mutated runtime")
	}
}

func TestNativeIndexedTransitionPreflightsAllNineLUTsBeforePublish(t *testing.T) {
	assets, field, state := completeNativeMapFrameFixture(t)
	assets.LUTs[2] = assets.LUTs[2][:255]
	actor := *state.Units[0]
	g := &Game{
		nativeMapAssets: assets, m: field,
		storyActors:   []battle.Unit{actor},
		nativeMapWork: []byte{7}, nativeMapVGA: []byte{8},
	}
	beforeWork, beforeVGA := append([]byte(nil), g.nativeMapWork...), append([]byte(nil), g.nativeMapVGA...)
	if err := g.startNativeIndexedTransition(nativeIndexedTransitionSpecForTest(), nil); err == nil {
		t.Fatal("malformed second-to-last LUT was accepted")
	}
	if g.indexedTransition != nil || !bytes.Equal(g.nativeMapWork, beforeWork) || !bytes.Equal(g.nativeMapVGA, beforeVGA) {
		t.Fatal("failed nine-LUT preflight partially published transition")
	}
}
