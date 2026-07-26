package indexedmap

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

const nativeMapHUDPanelEntry = 130

const (
	nativeMapHUDPositiveSignEntry = 0x83
	nativeMapHUDNegativeSignEntry = 0x84
)

// NativeMapHUDFrames is the mixed-codec subset of FDOTHER #5 used by
// 0x1acf3/0x1aeb1. These entries are deliberately Frame values, not LMI1Entry:
// native sends them to 0x4e63d's four-mode RLE decoder.
type NativeMapHUDFrames struct {
	Panel, PositiveSign, NegativeSign fdother.Frame
}

// DecodeNativeMapHUDFrames loads only the verified FDOTHER #5 directory
// entries. It avoids the incorrect assumption that all LMI1 entries share
// ParseLMI1's 0x4e916 cell codec.
func DecodeNativeMapHUDFrames(datPath string) (NativeMapHUDFrames, error) {
	panel, err := fdother.DecodeLMI1FrameResource(datPath, 5, nativeMapHUDPanelEntry)
	if err != nil {
		return NativeMapHUDFrames{}, err
	}
	positive, err := fdother.DecodeLMI1FrameResource(datPath, 5, nativeMapHUDPositiveSignEntry)
	if err != nil {
		return NativeMapHUDFrames{}, err
	}
	negative, err := fdother.DecodeLMI1FrameResource(datPath, 5, nativeMapHUDNegativeSignEntry)
	if err != nil {
		return NativeMapHUDFrames{}, err
	}
	return NativeMapHUDFrames{Panel: panel, PositiveSign: positive, NegativeSign: negative}, nil
}

// BlitNativeMapHUDPanel performs the proven first draw of 0x1acf3: both raw
// display gates must be nonzero, then FDOTHER #5 LMI1 entry #130 (69x34) is
// transparently blitted at the recovered 456-stride panel origin.  Terrain
// icon, unit icon, signed numbers and the higher-level meanings of the gates
// remain separate primitives; this function deliberately does not fabricate
// them from the panel artwork.
func BlitNativeMapHUDPanel(frames NativeMapHUDFrames, dst []byte, displayGateA, displayGateB bool, anchorX int) error {
	if !displayGateA || !displayGateB {
		return nil
	}
	layout, err := fdicon.NativeMapHUDLayoutFor(anchorX, fdicon.NativeMapStride)
	if err != nil {
		return err
	}
	panel := frames.Panel
	if panel.Width != 69 || panel.Height != 34 {
		return errors.New("indexedmap: native map HUD panel geometry differs from entry #130")
	}
	return panel.BlitAt(dst, fdicon.NativeMapStride, layout.Frame, -1)
}

// BlitNativeMapHUDSignedNumber preserves 0x1aeb1's raw sign selector: a
// nonnegative value uses LMI1 #0x83 (6x7), a negative value uses #0x84
// (6x5), then native passes the absolute value to its decimal renderer at a
// byte offset eight pixels to the right. drawDigits is mandatory so this
// primitive cannot silently omit the number while claiming a complete HUD.
//
// origin is an already-recovered framebuffer byte offset (for example the
// AP/DP origins from NativeMapHUDLayoutFor). The transaction uses a clone so
// a failing digit callback cannot leave only a sign on the caller's buffer.
func BlitNativeMapHUDSignedNumber(frames NativeMapHUDFrames, dst []byte, origin, value int, drawDigits func(dst []byte, origin, absolute int) error) error {
	if drawDigits == nil || origin < 0 || origin >= len(dst) {
		return errors.New("indexedmap: incomplete native map HUD signed number")
	}
	sign := frames.PositiveSign
	absolute := value
	if value < 0 {
		// Avoid wrapping the one signed integer native-sized arithmetic cannot
		// represent in the editable adapter.
		if value == -int(^uint(0)>>1)-1 {
			return errors.New("indexedmap: native map HUD signed value overflows")
		}
		sign, absolute = frames.NegativeSign, -value
	}
	wantHeight := 7
	if value < 0 {
		wantHeight = 5
	}
	if sign.Width != 6 || sign.Height != wantHeight {
		return errors.New("indexedmap: native map HUD sign geometry differs from LMI entries")
	}
	frame := append([]byte(nil), dst...)
	if err := sign.BlitAt(frame, fdicon.NativeMapStride, origin, -1); err != nil {
		return err
	}
	if err := drawDigits(frame, origin+8, absolute); err != nil {
		return err
	}
	copy(dst, frame)
	return nil
}
