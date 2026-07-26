package indexedmap

import (
	"errors"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

const nativeMapHUDPanelEntry = 130

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
