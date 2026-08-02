package main

import (
	"bytes"
	"testing"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/indexedmap"
)

func TestNativePaletteRampExecutesExactOutAndInEndpoints(t *testing.T) {
	assets, _, _ := completeNativeMapFrameFixture(t)
	for i := range assets.PaletteDAC {
		assets.PaletteDAC[i] = byte(i % 64)
	}
	g := &Game{
		nativeMapAssets: assets,
		nativeMapVGA:    bytes.Repeat([]byte{7}, indexedmap.NativeMapVGASize),
		nativeMapDAC:    append([]byte(nil), assets.PaletteDAC...),
	}
	advanced := 0
	if err := g.startNativePaletteRamp(0, 63, 2, func() { advanced++ }); err != nil {
		t.Fatal(err)
	}
	if got := len(g.nativePaletteRamp.deltas); got != 64 || g.nativePaletteRamp.deltas[0] != 0 || g.nativePaletteRamp.deltas[63] != 63 {
		t.Fatalf("fade-out deltas=%v", g.nativePaletteRamp.deltas)
	}
	for g.nativePaletteRamp != nil {
		g.nativePaletteRamp.drawn = true
		g.stepNativePaletteRamp()
	}
	if advanced != 1 || !nativeDACIsBlack(g.nativeMapDAC) {
		t.Fatalf("fade-out completion advanced=%d black=%v", advanced, nativeDACIsBlack(g.nativeMapDAC))
	}
	if err := g.startNativePaletteRamp(64, 0, 2, func() { advanced++ }); err != nil {
		t.Fatal(err)
	}
	if got := len(g.nativePaletteRamp.deltas); got != 65 || g.nativePaletteRamp.deltas[0] != 64 || g.nativePaletteRamp.deltas[64] != 0 {
		t.Fatalf("fade-in deltas=%v", g.nativePaletteRamp.deltas)
	}
	for g.nativePaletteRamp != nil {
		g.nativePaletteRamp.drawn = true
		g.stepNativePaletteRamp()
	}
	if advanced != 2 || !bytes.Equal(g.nativeMapDAC, assets.PaletteDAC) {
		t.Fatalf("fade-in completion advanced=%d baseline=%v", advanced, bytes.Equal(g.nativeMapDAC, assets.PaletteDAC))
	}
}

func TestNativePaletteRampDrawAcknowledgesIndexedFrame(t *testing.T) {
	assets, _, _ := completeNativeMapFrameFixture(t)
	for i := range assets.PaletteDAC {
		assets.PaletteDAC[i] = 0
	}
	assets.PaletteDAC[7*3] = 63
	g := &Game{
		nativeMapAssets: assets,
		nativeMapVGA:    bytes.Repeat([]byte{7}, indexedmap.NativeMapVGASize),
		nativeMapDAC:    append([]byte(nil), assets.PaletteDAC...),
	}
	if err := g.startNativePaletteRamp(0, 0, 2, nil); err != nil {
		t.Fatal(err)
	}
	r, green, blue, alpha := g.nativePaletteRamp.palette[7].RGBA()
	if r < 0xff00 || green != 0 || blue != 0 || alpha != 0xffff {
		t.Fatalf("indexed DAC palette=(%#x,%#x,%#x,%#x), want opaque red", r, green, blue, alpha)
	}
	screen := ebiten.NewImage(640, 400)
	if !g.drawNativePaletteRamp(screen) || !g.nativePaletteRamp.drawn {
		t.Fatal("indexed palette frame was not acknowledged by Draw")
	}
}

func TestChapter9PostDirectRecordPatchPreservesSparseRawWrites(t *testing.T) {
	beats, issues, err := campaign.CompileHandlerBinding("../../assets/cutscenes/bindings/ch09_post.json")
	if err != nil || len(issues) != 0 {
		t.Fatalf("ch09_post err=%v issues=%#v", err, issues)
	}
	var patch *campaign.HandlerDirectRecordPatch
	for _, beat := range beats {
		if beat.Op == "direct_record_patch" {
			patch = beat.DirectRecordPatch
		}
	}
	if patch == nil {
		t.Fatal("ch09_post direct record patch missing")
	}
	units := make([]*battle.Unit, 60)
	for i := range units {
		units[i] = &battle.Unit{
			X: 1, Y: 2, Dir: 1,
			NativeMapPresentation:    battle.NativeMapPresentationState{X: 1, Y: 2, Pose: 1, Motion: 3},
			HasNativeMapPresentation: true,
			NativeRecordByte5:        0x81, HasNativeRecordByte5: true,
			NativeTransient: [6]byte{1, 2, 3, 4, 5, 6},
		}
	}
	g := &Game{m: &MapData{W: 30, H: 50, TileW: 24, TileH: 24}, st: &battle.State{W: 30, H: 50, Units: units}}
	if err := g.applyHandlerDirectRecordPatch(patch); err != nil {
		t.Fatal(err)
	}
	if units[0].X != 14 || units[0].Y != 38 || units[0].Dir != 2 || units[0].NativeMapPresentation.Motion != 3 ||
		units[5].NativeRecordByte5 != 0 || units[50].NativeTransient[4] != 0 || units[51].NativeTransient[4] != 0 ||
		units[52].NativeRecordByte5 != 0 || units[50].NativeMapPresentation.Pose != 1 || units[52].NativeMapPresentation.Motion != 3 {
		t.Fatalf("sparse patch projection slots0=%#v 5=%#v 50=%#v 51=%#v 52=%#v", units[0], units[5], units[50], units[51], units[52])
	}
	view := g.st.NativeMapViewState
	if !g.st.HasNativeMapViewState || view.CameraX != 9 || view.CameraY != 34 || view.CursorX != 9 || view.CursorY != 34 || view.VisibleCursorX != 0 || view.VisibleCursorY != 0 || g.camX != 216 || g.camY != 816 {
		t.Fatalf("native view=%#v cam=(%v,%v)", view, g.camX, g.camY)
	}
}

func TestChapter9PostDirectRecordPatchFailsAtomicallyBelowFrontier(t *testing.T) {
	value := 9
	patch := &campaign.HandlerDirectRecordPatch{Units: []campaign.HandlerUnitRecordPatch{{Slot: 52, X: &value, Y: &value}}}
	units := make([]*battle.Unit, 52)
	for i := range units {
		units[i] = &battle.Unit{X: 1, Y: 2, NativeMapPresentation: battle.NativeMapPresentationState{X: 1, Y: 2}, HasNativeMapPresentation: true}
	}
	g := &Game{st: &battle.State{Units: units}}
	if err := g.applyHandlerDirectRecordPatch(patch); err == nil {
		t.Fatal("short runtime frontier accepted")
	}
	if units[0].X != 1 || units[0].Y != 2 {
		t.Fatal("rejected patch mutated an earlier slot")
	}
}

func TestChapter9PostDirectRecordPatchRejectsLateInvalidByteAtomically(t *testing.T) {
	x, y := 9, 10
	patch := &campaign.HandlerDirectRecordPatch{Units: []campaign.HandlerUnitRecordPatch{
		{Slot: 0, X: &x, Y: &y},
		{Slot: 1, RawBytes: []campaign.HandlerRawUnitBytePatch{{Offset: 5, Value: 0x100}}},
	}}
	units := []*battle.Unit{
		{X: 1, Y: 2, NativeMapPresentation: battle.NativeMapPresentationState{X: 1, Y: 2}, HasNativeMapPresentation: true},
		{NativeRecordByte5: 0x81, HasNativeRecordByte5: true},
	}
	g := &Game{st: &battle.State{Units: units}}
	if err := g.applyHandlerDirectRecordPatch(patch); err == nil {
		t.Fatal("out-of-range raw byte accepted")
	}
	if units[0].X != 1 || units[0].Y != 2 || units[1].NativeRecordByte5 != 0x81 {
		t.Fatalf("rejected patch mutated records: slot0=%#v slot1=%#v", units[0], units[1])
	}
}

func TestChapter19PostDirectRecordPatchPreservesExactNativeTables(t *testing.T) {
	beats, issues, err := campaign.CompileHandlerBinding("../../assets/cutscenes/bindings/ch19_post.json")
	if err != nil || len(issues) != 0 {
		t.Fatalf("ch19_post err=%v issues=%#v", err, issues)
	}
	var patch *campaign.HandlerDirectRecordPatch
	for _, beat := range beats {
		if beat.Op == "direct_record_patch" {
			patch = beat.DirectRecordPatch
		}
	}
	if patch == nil {
		t.Fatal("ch19_post direct record patch missing")
	}
	units := make([]*battle.Unit, 83)
	for i := range units {
		units[i] = &battle.Unit{
			X: 7, Y: 8, Dir: 2,
			NativeMapPresentation:    battle.NativeMapPresentationState{X: 7, Y: 8, Pose: 2, Motion: 9},
			HasNativeMapPresentation: true,
		}
	}
	g := &Game{m: &MapData{W: 50, H: 50, TileW: 24, TileH: 24}, st: &battle.State{W: 50, H: 50, Units: units}}
	if err := g.applyHandlerDirectRecordPatch(patch); err != nil {
		t.Fatal(err)
	}
	want := map[int][3]int{
		0: {33, 35, 1}, 10: {35, 37, 1}, 15: {36, 37, 1},
		52: {30, 35, 3}, 57: {28, 33, 3}, 60: {29, 34, 3},
	}
	for slot, expected := range want {
		u := units[slot]
		if u.X != expected[0] || u.Y != expected[1] || u.Dir != expected[2] || u.NativeMapPresentation.Motion != 9 {
			t.Fatalf("slot%d=(%d,%d,pose%d,motion%d), want (%d,%d,pose%d,motion9)", slot, u.X, u.Y, u.Dir, u.NativeMapPresentation.Motion, expected[0], expected[1], expected[2])
		}
	}
	for _, slot := range []int{16, 51, 61, 82} {
		if units[slot].X != 7 || units[slot].Y != 8 || units[slot].Dir != 2 {
			t.Fatalf("unwritten slot%d changed: %#v", slot, units[slot])
		}
	}
	view := g.st.NativeMapViewState
	if !g.st.HasNativeMapViewState || view.CameraX != 26 || view.CameraY != 31 ||
		view.CursorX != 26 || view.CursorY != 31 || view.VisibleCursorX != 0 ||
		view.VisibleCursorY != 0 || g.camX != 624 || g.camY != 744 {
		t.Fatalf("ch19 native view=%#v cam=(%v,%v)", view, g.camX, g.camY)
	}
}

func TestNativePaletteRampUsesBaselineSubtraction(t *testing.T) {
	baseline := bytes.Repeat([]byte{63}, 256*3)
	dac := append([]byte(nil), baseline...)
	if err := fdother.ApplyVGAPaletteSubtraction(dac, baseline, 0, 255, 63); err != nil || !nativeDACIsBlack(dac) {
		t.Fatalf("terminal subtraction err=%v black=%v", err, nativeDACIsBlack(dac))
	}
}
