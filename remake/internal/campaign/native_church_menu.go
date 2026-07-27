package campaign

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

const (
	nativeChurchMenuStride = 320
	nativeChurchMenuBase   = 169*320 + 240
)

var nativeChurchMenuOffsets = [4]int{-39, -13, 13, 39}

// NativeChurchMenuBase clears the exact 0x2d669 source rectangle before the
// four service cells are drawn.
func NativeChurchMenuBase(background []byte) ([]byte, error) {
	if len(background) != nativeChurchMenuStride*200 {
		return nil, errors.New("campaign: native church menu background must be 320x200")
	}
	frame := append([]byte(nil), background...)
	for y := 169; y < 189; y++ {
		for x := 201; x < 305; x++ {
			frame[y*nativeChurchMenuStride+x] = 0x4a
		}
	}
	return frame, nil
}

// NativeChurchMenuTransitionFrames reproduces 0x2d669's four independent
// restore/blit/present passes. FDOTHER#14 LMI1 entries 3/5/7/9 are the normal
// cells. Opening expands by divisors 4,3,2,1; closing contracts by 1,2,3,4.
func NativeChurchMenuTransitionFrames(
	background []byte,
	entries []fdother.LMI1Entry,
	opening bool,
) ([][]byte, error) {
	base, err := NativeChurchMenuBase(background)
	if err != nil {
		return nil, err
	}
	if len(entries) <= 10 {
		return nil, errors.New("campaign: FDOTHER#14 lacks church menu cells")
	}
	frames := make([][]byte, 0, 4)
	for pass := 0; pass < 4; pass++ {
		divisor := pass + 1
		if opening {
			divisor = 4 - pass
		}
		frame := append([]byte(nil), base...)
		for option, offset := range nativeChurchMenuOffsets {
			if err := blitNativeChurchMenuCell(frame, entries[2*option+3], offset/divisor); err != nil {
				return nil, err
			}
		}
		frames = append(frames, frame)
	}
	return frames, nil
}

// ComposeNativeChurchMenuFrame reproduces 0x2d85f mode zero after its initial
// normal-cell pass: only the selected option changes to its paired pulse cell.
func ComposeNativeChurchMenuFrame(
	background []byte,
	entries []fdother.LMI1Entry,
	selected, pulse int,
) ([]byte, error) {
	frame, err := NativeChurchMenuBase(background)
	if err != nil {
		return nil, err
	}
	if len(entries) <= 10 || selected < 0 || selected > 3 || pulse < 0 || pulse > 1 {
		return nil, errors.New("campaign: invalid native church menu state")
	}
	for option, offset := range nativeChurchMenuOffsets {
		index := 2*option + 3
		if option == selected {
			index += pulse
		}
		if err := blitNativeChurchMenuCell(frame, entries[index], offset); err != nil {
			return nil, err
		}
	}
	return frame, nil
}

func blitNativeChurchMenuCell(frame []byte, cell fdother.LMI1Entry, offset int) error {
	origin := nativeChurchMenuBase + offset
	return cell.BlitAt(frame, nativeChurchMenuStride, origin%nativeChurchMenuStride, origin/nativeChurchMenuStride, false)
}
