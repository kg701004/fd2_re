// font.go — minimal standalone copy of cmd/fd2's TTF CJK renderer.
//
// This is intentionally duplicated (not imported) from cmd/fd2/font.go so
// this viewer stays a self-contained, zero-risk addition that cannot affect
// the main engine's build or behavior. If/when the objectives screen is
// wired into cmd/fd2's real campaign flow, this duplication should be
// removed in favor of importing a shared internal/uifont package instead.
package main

import (
	"image/color"
	"math"
	"os"

	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/text"
	"golang.org/x/image/font"
	"golang.org/x/image/font/opentype"
	"golang.org/x/image/font/sfnt"
)

// fontPaths mirrors cmd/fd2/font.go's search order, with the Windows CJK UI
// fonts (msjh.ttc = 微軟正黑體, mingliu.ttc fallback) that the original list
// was missing — see the matching comment added to cmd/fd2/font.go for why.
var fontPaths = []string{
	"assets/fonts/cjk.ttc",
	"assets/fonts/cjk.otf",
	"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
	"/usr/share/fonts/truetype/arphic/uming.ttc",
	`C:\Windows\Fonts\msjh.ttc`,
	`C:\Windows\Fonts\mingliu.ttc`,
}

const fontSize = 20.0

type Font struct {
	sf    *sfnt.Font
	base  float64
	faces map[int]font.Face
	ascs  map[int]float64
}

func loadFont() *Font {
	var data []byte
	for _, p := range fontPaths {
		if d, e := os.ReadFile(p); e == nil {
			data = d
			break
		}
	}
	if data == nil {
		return nil
	}
	var sf *sfnt.Font
	if coll, err := sfnt.ParseCollection(data); err == nil {
		if f0, e := coll.Font(0); e == nil {
			sf = f0
		}
	}
	if sf == nil {
		if f0, err := sfnt.Parse(data); err == nil {
			sf = f0
		}
	}
	if sf == nil {
		return nil
	}
	return &Font{sf: sf, base: fontSize, faces: map[int]font.Face{}, ascs: map[int]float64{}}
}

func (f *Font) faceFor(px int) (font.Face, float64) {
	if px < 6 {
		px = 6
	}
	if fc, ok := f.faces[px]; ok {
		return fc, f.ascs[px]
	}
	fc, err := opentype.NewFace(f.sf, &opentype.FaceOptions{Size: float64(px), DPI: 72, Hinting: font.HintingFull})
	if err != nil || fc == nil {
		return nil, 0
	}
	asc := float64(fc.Metrics().Ascent.Round())
	f.faces[px] = fc
	f.ascs[px] = asc
	return fc, asc
}

func (f *Font) Draw(dst *ebiten.Image, s string, x, y, scale float64, clr color.RGBA) {
	px := int(math.Round(f.base * scale))
	face, asc := f.faceFor(px)
	if face == nil {
		return
	}
	op := &ebiten.DrawImageOptions{}
	op.GeoM.Translate(math.Round(x), math.Round(y)+asc)
	op.ColorScale.ScaleWithColor(clr)
	text.DrawWithOptions(dst, s, face, op)
}

func (f *Font) Width(s string, scale float64) float64 {
	px := int(math.Round(f.base * scale))
	face, _ := f.faceFor(px)
	if face == nil {
		return 0
	}
	return float64(text.BoundString(face, s).Dx())
}

func (f *Font) LineHeight(scale float64) float64 { return f.base * 1.5 * scale }
