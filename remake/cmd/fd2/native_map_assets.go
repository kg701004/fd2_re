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
	Palette  color.Palette
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
	paletteRaw, err := fdother.ReadResource(fdotherPath, 0)
	if err != nil {
		return nil, err
	}
	palette, err := fdother.ParseVGAPalette(paletteRaw)
	if err != nil {
		return nil, err
	}
	return &nativeMapAssets{MapIndex: mapIndex, Frames: frames, Terrain: terrain, Units: units, Controls: controls, Palette: palette}, nil
}

func nativeMapAssetsAvailable(a *nativeMapAssets) bool {
	return a != nil && a.Terrain != nil && a.Units != nil && len(a.Controls) > 0 && len(a.Palette) == 256
}
