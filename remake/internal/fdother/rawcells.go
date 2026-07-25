package fdother

import (
	"encoding/binary"
	"errors"
	"fmt"
)

// RawCell is an uncompressed indexed cell stored in FDOTHER's untagged
// offset-bank form. FDOTHER #2 uses this form for the native action overlay.
// Palette index zero preserves the destination, matching 0x4e9e4.
type RawCell struct {
	Width, Height int
	Pixels        []byte
}

// DecodeRawCellResource reads a raw FDOTHER archive entry whose first u32 is
// the byte end of a u32-offset directory. It deliberately does not try this
// parser for LMI1 or frame-table resources.
func DecodeRawCellResource(datPath string, resource int) ([]RawCell, error) {
	data, err := ReadResource(datPath, resource)
	if err != nil {
		return nil, err
	}
	return ParseRawCellBank(data)
}

// ParseRawCellBank parses the untagged directory used by FDOTHER #2:
//
//	+0  u32 directory_end (= first cell offset)
//	+4  u32 next cell offset
//	...
//	cell: u16 width, u16 height, width*height raw indexed pixels
//
// Native 0x4e9e4 consumes exactly width*height bytes, so directory offsets
// define cell starts rather than compressed stream ends.
func ParseRawCellBank(data []byte) ([]RawCell, error) {
	if len(data) < 4 {
		return nil, errors.New("fdother: raw cell bank is too short")
	}
	directoryEnd := int(binary.LittleEndian.Uint32(data[:4]))
	if directoryEnd < 4 || directoryEnd%4 != 0 || directoryEnd > len(data) {
		return nil, errors.New("fdother: invalid raw cell directory")
	}
	count := directoryEnd / 4
	cells := make([]RawCell, count)
	previous := directoryEnd
	for i := 0; i < count; i++ {
		off := int(binary.LittleEndian.Uint32(data[4*i:]))
		if off < previous || off+4 > len(data) {
			return nil, fmt.Errorf("fdother: raw cell %d offset is invalid", i)
		}
		width := int(binary.LittleEndian.Uint16(data[off:]))
		height := int(binary.LittleEndian.Uint16(data[off+2:]))
		if width <= 0 || height <= 0 || width > (len(data)-off-4)/height {
			return nil, fmt.Errorf("fdother: raw cell %d geometry is invalid", i)
		}
		end := off + 4 + width*height
		if end > len(data) {
			return nil, fmt.Errorf("fdother: raw cell %d pixels exceed resource", i)
		}
		cells[i] = RawCell{Width: width, Height: height, Pixels: data[off+4 : end]}
		previous = off
	}
	return cells, nil
}

// BlitAt applies 0x4e9e4's direct indexed copy. Zero source pixels leave the
// destination intact; the routine has no inferred palette conversion.
func (c RawCell) BlitAt(dst []byte, stride, x, y int) error {
	if c.Width <= 0 || c.Height <= 0 || len(c.Pixels) != c.Width*c.Height {
		return errors.New("fdother: invalid raw cell")
	}
	if x < 0 || y < 0 || stride < x+c.Width || y > len(dst)/stride || c.Height > (len(dst)-y*stride)/stride {
		return errors.New("fdother: raw cell destination is too small")
	}
	for row := 0; row < c.Height; row++ {
		for col := 0; col < c.Width; col++ {
			v := c.Pixels[row*c.Width+col]
			if v != 0 {
				dst[(y+row)*stride+x+col] = v
			}
		}
	}
	return nil
}
