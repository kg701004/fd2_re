// compose-map-image renders one map's full tile layout (from map.json's
// "tiles" index array + its ORIGINAL, pre-upscale tileset.png) into a single
// flat native-resolution PNG. This exists so Real-ESRGAN can be run once
// over the WHOLE map -- seeing true tile-to-tile adjacency -- instead of
// over each tile in isolation on the tileset sheet (which produced visible
// seams where identical tiles repeat at different map positions, since the
// model has no way to know what will end up next to what at render time).
//
// Usage:
//
//	go run ./cmd/compose-map-image <map dir> <original tileset.png> <out.png>
//
// <map dir> must contain map.json. <original tileset.png> is normally that
// same map's tileset.png.orig4x backup (the pre-upscale source), not the
// already-HD-swapped live tileset.png -- compositing from the already
// upscaled tiles would just reproduce the same isolated-tile seams this
// tool exists to avoid.
package main

import (
	"encoding/json"
	"fmt"
	"image"
	"image/draw"
	"image/png"
	"os"
)

type mapData struct {
	W, H, TileW, TileH, Cols int
	Tiles                    []int
}

func main() {
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: compose-map-image <map dir> <original tileset.png> <out.png>")
		os.Exit(1)
	}
	mapDir, tilesetPath, outPath := os.Args[1], os.Args[2], os.Args[3]

	raw, err := os.ReadFile(mapDir + "/map.json")
	check(err)
	var m mapData
	check(json.Unmarshal(raw, &m))
	if m.W <= 0 || m.H <= 0 || m.TileW <= 0 || m.TileH <= 0 || len(m.Tiles) != m.W*m.H {
		fmt.Fprintf(os.Stderr, "compose-map-image: invalid map data in %s\n", mapDir)
		os.Exit(1)
	}

	tsFile, err := os.Open(tilesetPath)
	check(err)
	tileset, err := png.Decode(tsFile)
	check(err)
	tsFile.Close()

	cols := m.Cols
	if cols == 0 {
		cols = tileset.Bounds().Dx() / m.TileW
	}

	out := image.NewRGBA(image.Rect(0, 0, m.W*m.TileW, m.H*m.TileH))
	for cy := 0; cy < m.H; cy++ {
		for cx := 0; cx < m.W; cx++ {
			idx := m.Tiles[cy*m.W+cx]
			if idx < 0 {
				continue
			}
			sx, sy := (idx%cols)*m.TileW, (idx/cols)*m.TileH
			srcRect := image.Rect(sx, sy, sx+m.TileW, sy+m.TileH)
			dstPt := image.Pt(cx*m.TileW, cy*m.TileH)
			draw.Draw(out, image.Rectangle{Min: dstPt, Max: dstPt.Add(srcRect.Size())}, tileset, srcRect.Min, draw.Src)
		}
	}

	outFile, err := os.Create(outPath)
	check(err)
	check(png.Encode(outFile, out))
	check(outFile.Close())
	fmt.Printf("%s: %dx%d tiles -> %s (%dx%d px)\n", mapDir, m.W, m.H, outPath, out.Bounds().Dx(), out.Bounds().Dy())
}

func check(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
