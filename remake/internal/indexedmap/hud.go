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

// BlitNativeMapHUDPanel performs the proven first draw of 0x1acf3: both raw
// display gates must be nonzero, then FDOTHER #5 LMI1 entry #130 (69x34) is
// transparently blitted at the recovered 456-stride panel origin.  Terrain
// icon, unit icon, signed numbers and the higher-level meanings of the gates
// remain separate primitives; this function deliberately does not fabricate
// them from the panel artwork.
func BlitNativeMapHUDPanel(entries []fdother.LMI1Entry, dst []byte, displayGateA, displayGateB bool, anchorX int) error {
	if !displayGateA || !displayGateB {
		return nil
	}
	if len(entries) <= nativeMapHUDPanelEntry {
		return errors.New("indexedmap: native map HUD panel entry is absent")
	}
	layout, err := fdicon.NativeMapHUDLayoutFor(anchorX, fdicon.NativeMapStride)
	if err != nil {
		return err
	}
	panel := entries[nativeMapHUDPanelEntry]
	if panel.Width != 69 || panel.Height != 34 {
		return errors.New("indexedmap: native map HUD panel geometry differs from entry #130")
	}
	return panel.BlitAt(dst, fdicon.NativeMapStride, layout.Frame%fdicon.NativeMapStride, layout.Frame/fdicon.NativeMapStride, false)
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
func BlitNativeMapHUDSignedNumber(entries []fdother.LMI1Entry, dst []byte, origin, value int, drawDigits func(dst []byte, origin, absolute int) error) error {
	if drawDigits == nil || len(entries) <= nativeMapHUDNegativeSignEntry || origin < 0 || origin >= len(dst) {
		return errors.New("indexedmap: incomplete native map HUD signed number")
	}
	entry := nativeMapHUDPositiveSignEntry
	absolute := value
	if value < 0 {
		// Avoid wrapping the one signed integer native-sized arithmetic cannot
		// represent in the editable adapter.
		if value == -int(^uint(0)>>1)-1 {
			return errors.New("indexedmap: native map HUD signed value overflows")
		}
		entry, absolute = nativeMapHUDNegativeSignEntry, -value
	}
	sign := entries[entry]
	wantHeight := 7
	if entry == nativeMapHUDNegativeSignEntry {
		wantHeight = 5
	}
	if sign.Width != 6 || sign.Height != wantHeight {
		return errors.New("indexedmap: native map HUD sign geometry differs from LMI entries")
	}
	frame := append([]byte(nil), dst...)
	if err := sign.BlitAt(frame, fdicon.NativeMapStride, origin%fdicon.NativeMapStride, origin/fdicon.NativeMapStride, false); err != nil {
		return err
	}
	if err := drawDigits(frame, origin+8, absolute); err != nil {
		return err
	}
	copy(dst, frame)
	return nil
}
