// Package indexedmap composes the verified steady native tactical-map passes.
// It intentionally has no Ebiten dependency: callers supply indexed buffers
// and the still-separate native HUD pass.
package indexedmap

import (
	"errors"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

const (
	workStride = fdicon.NativeMapStride
	workBase   = 0x8088
	viewWidth  = 320
	viewHeight = 192
)

// FrameInput is the raw, already-selected input required by 0x11cac's normal
// redraw.  It deliberately keeps all native selectors raw: the caller owns
// resource selection, map lifetime, palette phase, and unit materialization.
type FrameInput struct {
	TerrainBank, RangeBank, UnitBank, ForegroundBank *fdicon.Bank
	SelectorCache                                    *fdicon.NativeSelectorCache
	Cells                                            []fdicon.NativeTerrainCell
	Controls, LUT                                    []byte
	MapWidth, CameraX, CameraY                       int
	Flip, TerrainCycle, IdleCycle, MovingCycle       int
	PixelShift                                       int
	RangeMode, CursorX, CursorY                      int
	Units                                            []fdicon.NativeUnitLayerEntry
	ForegroundUnits                                  []fdicon.NativeForegroundLayerEntry
}

// NativeFrameInput is the complete, directly composable steady redraw slice.
// It binds the separately verified 0x1acf3 resources/input to 0x11cac's
// terrain/range/unit/foreground scheduler without allowing a caller to swap
// in an approximation at the HUD boundary.
type NativeFrameInput struct {
	Frame                FrameInput
	HUD                  NativeMapHUDInput
	Frames               NativeMapHUDFrames
	HUDTerrain, HUDUnits *fdicon.Bank
	HUDCache             *fdicon.NativeSelectorCache
}

// ComposeNativeFrame is the strict native-HUD form of ComposeFrame. It uses
// the exact indexed HUD assembly at its recovered position, rather than
// accepting an arbitrary callback. All source data remain explicit and any
// rejection keeps work/VGA unchanged through ComposeFrame's transaction.
func ComposeNativeFrame(work, vga []byte, in NativeFrameInput) error {
	return ComposeFrame(work, vga, in.Frame, func(dst []byte) error {
		return BlitNativeMapHUD(in.Frames, in.HUDTerrain, in.HUDUnits, in.HUDCache, dst, in.HUD)
	})
}

// ComposeFrame performs the recovered steady order:
//
//	0x11eee terrain → 0x122dc range → 0x127a9 unit/foreground
//	→ required 0x1acf3-equivalent HUD callback → 0x11eb0 viewport copy.
//
// HUD is mandatory because copying before it would silently alter native draw
// order. All work happens on a private clone first, so rejected editable input
// or a HUD error never leaves either caller buffer partially changed.
func ComposeFrame(work, vga []byte, in FrameInput, renderHUD func([]byte) error) error {
	if renderHUD == nil || len(work)%workStride != 0 || len(vga) < viewWidth*viewHeight || in.MapWidth <= 0 || len(in.Cells)%in.MapWidth != 0 {
		return errors.New("indexedmap: incomplete native frame input")
	}
	if in.TerrainBank == nil || in.RangeBank == nil || in.UnitBank == nil || in.ForegroundBank == nil || in.SelectorCache == nil {
		return errors.New("indexedmap: missing native frame bank")
	}
	frame := append([]byte(nil), work...)
	baseX, baseY := workBase%workStride, workBase/workStride
	if err := in.TerrainBank.BlitNativeTerrainRegion(frame, workStride, baseX, baseY, in.MapWidth, in.Cells, in.Controls, in.CameraX, in.CameraY, 13, 8, in.Flip, in.TerrainCycle, in.LUT); err != nil {
		return fmt.Errorf("indexedmap: terrain: %w", err)
	}
	if err := fdother.BlitNativeRangeOverlay(in.RangeBank, frame, in.CameraX, in.CameraY, 13, 8, in.RangeMode, in.CursorX, in.CursorY); err != nil {
		return fmt.Errorf("indexedmap: range: %w", err)
	}
	if err := in.UnitBank.BlitNativeUnitLayer(frame, workStride, in.SelectorCache, in.Units, in.CameraX, in.CameraY, 12, 7, in.IdleCycle, in.MovingCycle, in.PixelShift); err != nil {
		return fmt.Errorf("indexedmap: units: %w", err)
	}
	if err := in.ForegroundBank.BlitNativeForegroundLayer(frame, workStride, in.ForegroundUnits, in.MapWidth, in.Cells, in.Controls, in.CameraX, in.CameraY, 12, 7, in.Flip, in.LUT); err != nil {
		return fmt.Errorf("indexedmap: foreground: %w", err)
	}
	if err := renderHUD(frame); err != nil {
		return fmt.Errorf("indexedmap: HUD: %w", err)
	}
	copyFrame := make([]byte, viewWidth*viewHeight)
	if err := fdicon.CopyNativeIndexedRegion(copyFrame, viewWidth, frame[workBase:], workStride, viewWidth, viewHeight); err != nil {
		return fmt.Errorf("indexedmap: viewport copy: %w", err)
	}
	copy(work, frame)
	copy(vga, copyFrame)
	return nil
}
