package indexedmap

import (
	"encoding/binary"
	"errors"
	"os"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func frame(width, height int, pixel byte) fdother.Frame {
	raw := make([]byte, 4)
	binary.LittleEndian.PutUint16(raw, uint16(width))
	binary.LittleEndian.PutUint16(raw[2:], uint16(height))
	for row := 0; row < height; row++ {
		for remaining := width; remaining > 0; {
			count := remaining
			if count > 64 {
				count = 64
			}
			raw = append(raw, byte(count-1), pixel)
			remaining -= count
		}
	}
	return fdother.Frame{Width: width, Height: height, Pixels: raw}
}

func hudFrames() NativeMapHUDFrames {
	frames := NativeMapHUDFrames{Panel: frame(69, 34, 0x5a), PositiveSign: frame(6, 7, 0x31), NegativeSign: frame(6, 5, 0x42)}
	for digit := range frames.Digits {
		frames.Digits[digit] = frame(6, 8, byte(0x50+digit))
	}
	frames.Digits[1] = frame(5, 8, 0x51) // FDOTHER #5 entry #0x20 is 5x8.
	return frames
}

func TestBlitNativeMapHUDPanelGatesAndOrigin(t *testing.T) {
	dst := make([]byte, fdicon.NativeMapStride*200)
	if err := BlitNativeMapHUDPanel(hudFrames(), dst, true, false, 1); err != nil {
		t.Fatal(err)
	}
	layout, _ := fdicon.NativeMapHUDLayoutFor(1, fdicon.NativeMapStride)
	if dst[layout.Frame] != 0 {
		t.Fatal("closed display gate drew panel")
	}
	if err := BlitNativeMapHUDPanel(hudFrames(), dst, true, true, 1); err != nil {
		t.Fatal(err)
	}
	if dst[layout.Frame] != 0x5a {
		t.Fatalf("panel byte=%#x, want %#x", dst[layout.Frame], 0x5a)
	}
}

func TestBlitNativeMapHUDPanelRejectsInvalidEntryBeforeWrite(t *testing.T) {
	frames := hudFrames()
	frames.Panel = frame(1, 1, 7)
	dst, before := make([]byte, fdicon.NativeMapStride*200), make([]byte, fdicon.NativeMapStride*200)
	if err := BlitNativeMapHUDPanel(frames, dst, true, true, 1); err == nil {
		t.Fatal("wrong panel geometry accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("rejected panel mutated destination")
	}
}

func TestBlitNativeMapHUDTerrainIconUses12E38TileAtPanelPlus6(t *testing.T) {
	terrain := bank(2, 0)
	terrain.Sprites[1] = solid(0x66)
	dst := make([]byte, fdicon.NativeMapStride*200)
	if err := BlitNativeMapHUDTerrainIcon(terrain, dst, 1, 1); err != nil {
		t.Fatal(err)
	}
	layout, _ := fdicon.NativeMapHUDLayoutFor(1, fdicon.NativeMapStride)
	if dst[layout.Terrain] != 0x66 {
		t.Fatalf("terrain icon=%#x", dst[layout.Terrain])
	}
	before := append([]byte(nil), dst...)
	if err := BlitNativeMapHUDTerrainIcon(terrain, dst, 1, 2); err == nil {
		t.Fatal("out-of-bank terrain descriptor accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("rejected terrain descriptor mutated HUD")
	}
}

func TestBlitNativeMapHUDUnitIconUsesCacheAndAliasesStateThree(t *testing.T) {
	cache := &fdicon.NativeSelectorCache{}
	if _, err := cache.SlotFor(0); err != nil {
		t.Fatal(err)
	}
	units := bank(12, 0)
	units.Sprites[1] = solid(0x77) // cache key 0, pose 0, aliased cycle 1
	dst := make([]byte, fdicon.NativeMapStride*200)
	if err := BlitNativeMapHUDUnitIcon(units, cache, dst, 1, 0, 3); err != nil {
		t.Fatal(err)
	}
	layout, _ := fdicon.NativeMapHUDLayoutFor(1, fdicon.NativeMapStride)
	if dst[layout.Unit] != 0x77 {
		t.Fatalf("unit icon=%#x", dst[layout.Unit])
	}
	before := append([]byte(nil), dst...)
	if err := BlitNativeMapHUDUnitIcon(units, cache, dst, 1, 0, 4); err == nil {
		t.Fatal("invalid raw state accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("rejected unit icon selector mutated HUD")
	}
}

func TestNativeMapHUDTerrainAPDPMatches1ACF3Tables(t *testing.T) {
	for code, want := range map[byte][2]int{0: {5, 0}, 1: {0, 0}, 2: {-5, 10}, 3: {-5, 10}, 4: {-5, -5}, 5: {0, 0}} {
		ap, dp, err := NativeMapHUDTerrainAPDP(code)
		if err != nil || [2]int{ap, dp} != want {
			t.Fatalf("code=%d got=(%d,%d) err=%v", code, ap, dp, err)
		}
	}
	if _, _, err := NativeMapHUDTerrainAPDP(6); err == nil {
		t.Fatal("invalid control byte accepted")
	}
}

func TestBlitNativeMapHUDTerrainAPDPUsesLayoutAndIsAtomic(t *testing.T) {
	dst := make([]byte, fdicon.NativeMapStride*200)
	if err := BlitNativeMapHUDTerrainAPDP(hudFrames(), dst, 1, 2); err != nil {
		t.Fatal(err)
	}
	layout, _ := fdicon.NativeMapHUDLayoutFor(1, fdicon.NativeMapStride)
	if dst[layout.AP] != 0x42 || dst[layout.AP+8] != 0x50 || dst[layout.AP+14] != 0x55 || dst[layout.DP] != 0x31 || dst[layout.DP+8] != 0x51 || dst[layout.DP+14] != 0x50 {
		t.Fatalf("unexpected AP/DP cells: AP=%#x/%#x/%#x DP=%#x/%#x/%#x", dst[layout.AP], dst[layout.AP+8], dst[layout.AP+14], dst[layout.DP], dst[layout.DP+8], dst[layout.DP+14])
	}
	before := append([]byte(nil), dst...)
	if err := BlitNativeMapHUDTerrainAPDP(hudFrames(), dst, 1, 6); err == nil {
		t.Fatal("invalid control byte accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("invalid terrain control mutated HUD")
	}
}

func TestBlitNativeMapHUDSignedNumberSelectsSignAndAbsoluteValue(t *testing.T) {
	dst := make([]byte, fdicon.NativeMapStride*30)
	calledOrigin, calledAbsolute := -1, -1
	draw := func(frame []byte, origin, absolute int) error {
		calledOrigin, calledAbsolute = origin, absolute
		frame[origin] = 0x5a
		return nil
	}
	origin := fdicon.NativeMapStride + 10
	if err := BlitNativeMapHUDSignedNumber(hudFrames(), dst, origin, 12, draw); err != nil {
		t.Fatal(err)
	}
	if dst[origin] != 0x31 || dst[origin+8] != 0x5a || calledOrigin != origin+8 || calledAbsolute != 12 {
		t.Fatalf("positive sign/digits mismatch: sign=%#x origin=%d absolute=%d", dst[origin], calledOrigin, calledAbsolute)
	}
	if err := BlitNativeMapHUDSignedNumber(hudFrames(), dst, origin, -9, draw); err != nil {
		t.Fatal(err)
	}
	if dst[origin] != 0x42 || calledAbsolute != 9 {
		t.Fatalf("negative sign/absolute mismatch: sign=%#x absolute=%d", dst[origin], calledAbsolute)
	}
}

func TestBlitNativeMapHUDSignedNumberIsAtomicOnDigitFailure(t *testing.T) {
	dst := make([]byte, fdicon.NativeMapStride*20)
	before := append([]byte(nil), dst...)
	if err := BlitNativeMapHUDSignedNumber(hudFrames(), dst, 1, 1, func([]byte, int, int) error { return errors.New("digits") }); err == nil {
		t.Fatal("digit failure accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("digit failure partially drew sign")
	}
}

func TestBlitNativeMapHUDTwoDigitNumberMatches187D6CallSlice(t *testing.T) {
	dst := make([]byte, fdicon.NativeMapStride*30)
	origin := fdicon.NativeMapStride + 10
	if err := BlitNativeMapHUDTwoDigitNumber(hudFrames(), dst, origin, -12); err != nil {
		t.Fatal(err)
	}
	if dst[origin] != 0x42 || dst[origin+8] != 0x51 || dst[origin+14] != 0x52 {
		t.Fatalf("sign/digits=%#x %#x %#x", dst[origin], dst[origin+8], dst[origin+14])
	}
	before := append([]byte(nil), dst...)
	if err := BlitNativeMapHUDTwoDigitNumber(hudFrames(), dst, origin, 100); err == nil {
		t.Fatal("three-digit value accepted")
	}
	if string(dst) != string(before) {
		t.Fatal("rejected value mutated HUD")
	}
}

func TestDecodeNativeMapHUDFramesUsesFourModeDirectoryEntries(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(datPath); os.IsNotExist(err) {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	frames, err := DecodeNativeMapHUDFrames(datPath)
	if err != nil {
		t.Fatal(err)
	}
	if frames.Panel.Width != 69 || frames.Panel.Height != 34 || frames.PositiveSign.Width != 6 || frames.PositiveSign.Height != 7 || frames.NegativeSign.Width != 6 || frames.NegativeSign.Height != 5 {
		t.Fatalf("frames=%#v", frames)
	}
	for i, digit := range frames.Digits {
		wantWidth := 6
		if i == 1 {
			wantWidth = 5
		}
		if digit.Width != wantWidth || digit.Height != 8 {
			t.Fatalf("digit %d=%dx%d", i, digit.Width, digit.Height)
		}
	}
	if err := BlitNativeMapHUDPanel(frames, make([]byte, fdicon.NativeMapStride*200), true, true, 1); err != nil {
		t.Fatal(err)
	}
}
