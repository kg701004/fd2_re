package fdother

import (
	"errors"
	"image"
	"image/color"
)

// ParseVGAPalette converts FDOTHER #0's 256×RGB six-bit DAC payload to a Go
// palette. Palette index zero is transparent because 0x4e9e4 preserves the
// destination for zero source pixels; all other entries are opaque.
func ParseVGAPalette(data []byte) (color.Palette, error) {
	if len(data) != 256*3 {
		return nil, errors.New("fdother: VGA palette must contain 768 bytes")
	}
	palette := make(color.Palette, 256)
	for i := range palette {
		r, g, b := data[3*i], data[3*i+1], data[3*i+2]
		if r > 63 || g > 63 || b > 63 {
			return nil, errors.New("fdother: VGA palette component exceeds six bits")
		}
		a := uint8(0xff)
		if i == 0 {
			a = 0
		}
		palette[i] = color.NRGBA{R: (r << 2) | (r >> 4), G: (g << 2) | (g >> 4), B: (b << 2) | (b >> 4), A: a}
	}
	return palette, nil
}

// Paletted returns an image form of a direct-indexed raw cell. Its zero index
// remains transparent, matching the native 0x4e9e4 destination-preserving
// blitter rather than turning transparent pixels into opaque black.
func (c RawCell) Paletted(palette color.Palette) (*image.Paletted, error) {
	if c.Width <= 0 || c.Height <= 0 || len(c.Pixels) != c.Width*c.Height {
		return nil, errors.New("fdother: invalid raw cell")
	}
	if len(palette) < 256 {
		return nil, errors.New("fdother: palette has fewer than 256 entries")
	}
	im := image.NewPaletted(image.Rect(0, 0, c.Width, c.Height), palette)
	copy(im.Pix, c.Pixels)
	return im, nil
}
