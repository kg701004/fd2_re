package fdother

import (
	"errors"
	"image"
	"image/color"
)

// ParseVGAPalette converts FDOTHER #0's 256×RGB six-bit DAC payload to an
// opaque VGA palette. Transparency is a property of individual native
// blitters/masks, not of a DAC index; a complete mode-13h framebuffer may
// legitimately contain visible palette index zero.
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
		palette[i] = color.NRGBA{R: (r << 2) | (r >> 4), G: (g << 2) | (g >> 4), B: (b << 2) | (b >> 4), A: 0xff}
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
	cellPalette := append(color.Palette(nil), palette...)
	r, g, b, _ := cellPalette[0].RGBA()
	cellPalette[0] = color.NRGBA{
		R: uint8(r >> 8), G: uint8(g >> 8), B: uint8(b >> 8), A: 0,
	}
	im := image.NewPaletted(image.Rect(0, 0, c.Width, c.Height), cellPalette)
	copy(im.Pix, c.Pixels)
	return im, nil
}
