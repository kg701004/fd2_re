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
	return NativeMapHUDFrames{Panel: frame(69, 34, 0x5a), PositiveSign: frame(6, 7, 0x31), NegativeSign: frame(6, 5, 0x42)}
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
	if err := BlitNativeMapHUDPanel(frames, make([]byte, fdicon.NativeMapStride*200), true, true, 1); err != nil {
		t.Fatal(err)
	}
}
