package fdother

import (
	"encoding/binary"
	"errors"
	"fmt"
)

// LMI1Entry is one indexed UI cell from FDOTHER.DAT resource #5.
// Pixels are decoded in row-major order; palette index 0 remains transparent
// to the caller, matching native 0x4e916/0x4e8af.
type LMI1Entry struct {
	Width, Height int
	Pixels        []byte
}

// DecodeLMI1Resource reads one player-provided FDOTHER archive entry and
// decodes it as an LMI1 UI container. It keeps the archive boundary explicit,
// just like DecodeResource does for frame-table entries.
func DecodeLMI1Resource(datPath string, resource int) ([]LMI1Entry, error) {
	data, err := ReadResource(datPath, resource)
	if err != nil {
		return nil, err
	}
	return ParseLMI1(data)
}

// BlitAt copies an LMI1 cell to an indexed destination using the native
// 0x4e8af transparent rule: palette index 0 preserves the destination.
// mirror applies the 0x4e8e1 horizontal reverse path. Coordinates are
// explicit so callers cannot accidentally infer the native panel anchor.
func (e LMI1Entry) BlitAt(dst []byte, stride, x, y int, mirror bool) error {
	if e.Width <= 0 || e.Height <= 0 || len(e.Pixels) != e.Width*e.Height {
		return errors.New("fdother: invalid LMI1 entry geometry")
	}
	if x < 0 || y < 0 || stride <= 0 || stride < x+e.Width || y > len(dst)/stride || e.Height > (len(dst)-y*stride)/stride {
		return errors.New("fdother: LMI1 destination is too small")
	}
	for row := 0; row < e.Height; row++ {
		for col := 0; col < e.Width; col++ {
			src := col
			if mirror {
				src = e.Width - 1 - col
			}
			v := e.Pixels[row*e.Width+src]
			if v != 0 {
				dst[(y+row)*stride+x+col] = v
			}
		}
	}
	return nil
}

// ParseLMI1 decodes the small indexed sub-resource container used by the
// native UI sprite bank. Its directory starts at byte 6 (after "LMI1" and a
// u16 count), and each entry is {u16 width, u16 height, 0xc0 codec stream}.
// The codec is intentionally kept separate from the FDOTHER frame-table RLE:
// bytes <= 0xc0 are literal pixels; bytes > 0xc0 mean (byte-0xc0) repeats of
// the following pixel byte.
func ParseLMI1(data []byte) ([]LMI1Entry, error) {
	if len(data) < 6 || string(data[:4]) != "LMI1" {
		return nil, errors.New("fdother: missing LMI1 magic")
	}
	count := int(binary.LittleEndian.Uint16(data[4:]))
	tableEnd := 6 + count*4
	if count == 0 || tableEnd > len(data) {
		return nil, errors.New("fdother: invalid LMI1 directory")
	}
	entries := make([]LMI1Entry, count)
	previous := tableEnd
	for i := 0; i < count; i++ {
		off := int(binary.LittleEndian.Uint32(data[6+i*4:]))
		end := len(data)
		if i+1 < count {
			end = int(binary.LittleEndian.Uint32(data[6+(i+1)*4:]))
		}
		if off < previous || off+4 > end || end > len(data) {
			return nil, fmt.Errorf("fdother: LMI1 entry %d bounds invalid", i)
		}
		w := int(binary.LittleEndian.Uint16(data[off:]))
		h := int(binary.LittleEndian.Uint16(data[off+2:]))
		if w <= 0 || h <= 0 {
			return nil, fmt.Errorf("fdother: LMI1 entry %d has empty dimensions", i)
		}
		// The LMI1 directory gives entry starts, not a strict compressed-stream
		// end. Native 0x4e916 reads until its width×height destination loop is
		// full, and a repeat may cross the next directory offset. Bound only at
		// the containing resource, matching that behavior.
		pixels, err := decodeLMI1Pixels(data[off+4:], w*h)
		if err != nil {
			return nil, fmt.Errorf("fdother: LMI1 entry %d: %w", i, err)
		}
		entries[i] = LMI1Entry{Width: w, Height: h, Pixels: pixels}
		previous = off
	}
	return entries, nil
}

func decodeLMI1Pixels(stream []byte, want int) ([]byte, error) {
	pixels := make([]byte, 0, want)
	for len(pixels) < want {
		if len(stream) == 0 {
			return nil, errors.New("codec stream ends before dimensions are filled")
		}
		c := stream[0]
		stream = stream[1:]
		if c <= 0xc0 {
			pixels = append(pixels, c)
			continue
		}
		run := int(c) - 0xc0
		if len(stream) == 0 {
			return nil, errors.New("repeat command lacks pixel value")
		}
		v := stream[0]
		stream = stream[1:]
		// 0x4e916 retains its repeat counter across scanlines. If a final
		// repeat crosses the cell boundary, the native width×height loop simply
		// stops consuming pixels; the surplus repeat state is discarded with
		// this blit. Mirror that bounded destination behavior here.
		if remain := want - len(pixels); run > remain {
			run = remain
		}
		for i := 0; i < run; i++ {
			pixels = append(pixels, v)
		}
	}
	return pixels, nil
}
