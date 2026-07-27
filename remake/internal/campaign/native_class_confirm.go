package campaign

import (
	"errors"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

const (
	nativeConfirmBaseX = 248
	nativeConfirmY     = 168
)

// NativeClassConfirmationOpeningFrames reproduces 0x19953's four opening
// presents with FDOTHER#2 raw cells 16/17.
func NativeClassConfirmationOpeningFrames(background []byte, cells []fdother.RawCell) ([][]byte, error) {
	if err := validateNativeClassConfirmationAssets(background, cells); err != nil {
		return nil, err
	}
	out := make([][]byte, 0, 4)
	for spread := 4; spread <= 16; spread += 4 {
		frame := append([]byte(nil), background...)
		if err := cells[16].BlitAt(frame, 320, nativeConfirmBaseX-spread, nativeConfirmY); err != nil {
			return nil, err
		}
		if err := cells[17].BlitAt(frame, 320, nativeConfirmBaseX+spread, nativeConfirmY); err != nil {
			return nil, err
		}
		out = append(out, frame)
	}
	return out, nil
}

// NativeClassConfirmationClosingFrames reproduces 0x197e5's four presented
// positions. The caller owns the post-close background restore.
func NativeClassConfirmationClosingFrames(background []byte, cells []fdother.RawCell) ([][]byte, error) {
	if err := validateNativeClassConfirmationAssets(background, cells); err != nil {
		return nil, err
	}
	out := make([][]byte, 0, 4)
	for spread := 12; spread >= 0; spread -= 4 {
		frame := append([]byte(nil), background...)
		if err := cells[16].BlitAt(frame, 320, nativeConfirmBaseX-spread, nativeConfirmY); err != nil {
			return nil, err
		}
		if err := cells[17].BlitAt(frame, 320, nativeConfirmBaseX+spread, nativeConfirmY); err != nil {
			return nil, err
		}
		out = append(out, frame)
	}
	return out, nil
}

// ComposeNativeClassConfirmationFrame draws FDTXT #594 with its verified
// FFFC dynamic-name substitution, then the normal/pulsed choice cells
// 48/49 and 51/52 used by 0x19953's input loop.
func ComposeNativeClassConfirmationFrame(
	background []byte,
	cells []fdother.RawCell,
	strings *fdtxt.Strings,
	font *fdtxt.Font,
	nameTextIndex, selected, pulse int,
) ([]byte, error) {
	if err := validateNativeClassConfirmationAssets(background, cells); err != nil {
		return nil, err
	}
	if selected < 0 || selected > 1 || pulse < 0 || pulse > 1 || strings == nil || font == nil {
		return nil, errors.New("campaign: invalid native class confirmation state")
	}
	question, err := strings.Words(594)
	if err != nil {
		return nil, err
	}
	name, err := strings.Words(nameTextIndex)
	if err != nil {
		return nil, err
	}
	expanded := make([]uint16, 0, len(name)+len(question)-1)
	for _, word := range question {
		if word == 0xfffc {
			expanded = append(expanded, name...)
			continue
		}
		if word >= fdtxt.ControlMin {
			return nil, fmt.Errorf("campaign: unsupported class confirmation control %#x", word)
		}
		expanded = append(expanded, word)
	}
	frame := append([]byte(nil), background...)
	style := fdtxt.NativeGlyphStyle{Foreground: 205, Shadow: 76}
	for i, word := range expanded {
		if word >= fdtxt.ControlMin {
			return nil, fmt.Errorf("campaign: dynamic class name contains control %#x", word)
		}
		if err := font.BlitNativeGlyph(frame, 320, 119*320+12+i*fdtxt.GlyphWidth, int(word), style); err != nil {
			return nil, err
		}
	}
	for option, base := range []int{48, 51} {
		index := base
		if option == selected {
			index += pulse
		}
		x := nativeConfirmBaseX + []int{-16, 16}[option]
		if err := cells[index].BlitAt(frame, 320, x, nativeConfirmY); err != nil {
			return nil, err
		}
	}
	return frame, nil
}

func validateNativeClassConfirmationAssets(background []byte, cells []fdother.RawCell) error {
	if len(background) != 320*200 || len(cells) <= 52 {
		return errors.New("campaign: native class confirmation assets are unavailable")
	}
	for _, index := range []int{16, 17, 48, 49, 51, 52} {
		wantHeight := 16
		if index == 16 || index == 17 {
			wantHeight = 20
		}
		if cells[index].Width != 24 || cells[index].Height != wantHeight {
			return fmt.Errorf("campaign: native class confirmation cell %d is %dx%d", index, cells[index].Width, cells[index].Height)
		}
	}
	return nil
}
