package main

import (
	"errors"
	"image/color"
	"path/filepath"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/indexedmap"
)

// nativeMapAssets is an all-or-nothing original-resource bundle. It remains
// separate from the PNG renderer until indexed presentation is ready.
type nativeMapAssets struct {
	MapIndex int
	Frames   indexedmap.NativeMapHUDFrames
	Terrain  *fdicon.Bank
	Units    *fdicon.Bank
	Controls []byte
	// LUTs is FDOTHER#3's raw 256-byte remap bank. Entries 1..9 are the
	// verified 0x24618 transition selectors; loading them here does not by
	// itself authorize scene presentation.
	LUTs    [][]byte
	Palette color.Palette
}

func loadNativeMapAssets(mapDir string) (*nativeMapAssets, error) {
	mapIndex, err := fdother.MapIndexFromAssetPath(mapDir)
	if err != nil {
		return nil, err
	}
	fdotherPath := nativeFDOTHERPath()
	if fdotherPath == "" {
		return nil, errors.New("native map assets: FDOTHER.DAT unavailable")
	}
	base := filepath.Dir(fdotherPath)
	frames, err := indexedmap.DecodeNativeMapHUDFrames(fdotherPath)
	if err != nil {
		return nil, err
	}
	terrain, controls, err := fdother.DecodeMapTerrainResources(filepath.Join(base, "FDSHAP.DAT"), mapIndex)
	if err != nil {
		return nil, err
	}
	units, err := fdicon.DecodeFile(filepath.Join(base, "FDICON.B24"))
	if err != nil {
		return nil, err
	}
	luts, err := fdother.DecodeLUTResource(fdotherPath, 3)
	if err != nil || len(luts) <= 9 {
		if err != nil {
			return nil, err
		}
		return nil, errors.New("native map assets: FDOTHER#3 LUT bank lacks transition entries 1..9")
	}
	paletteRaw, err := fdother.ReadResource(fdotherPath, 0)
	if err != nil {
		return nil, err
	}
	palette, err := fdother.ParseVGAPalette(paletteRaw)
	if err != nil {
		return nil, err
	}
	return &nativeMapAssets{MapIndex: mapIndex, Frames: frames, Terrain: terrain, Units: units, Controls: controls, LUTs: luts, Palette: palette}, nil
}

func nativeMapAssetsAvailable(a *nativeMapAssets) bool {
	return a != nil && a.Terrain != nil && a.Units != nil && len(a.Controls) > 0 && len(a.LUTs) > 9 && len(a.Palette) == 256
}
