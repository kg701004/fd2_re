package fdother

import (
	"encoding/binary"
	"errors"
	"fmt"
)

// LMI1Entry is one indexed UI cell from FDOTHER.DAT resource #5.
// Pixels are decoded in row-major order. Transparency is a property of the
// caller's blit primitive, not of the 0x4e916 decoder.
type LMI1Entry struct {
	Width, Height int
	Pixels        []byte
}

// ParseOpaqueRunCell decodes the width/height + 0x4e916 high-run payload used
// by callers of 0x4e8af. It is intentionally separate from ParseLMI1 because
// native scene resources may use an outer LLLLLL directory while retaining
// the same per-cell codec.
func ParseOpaqueRunCell(data []byte) (LMI1Entry, error) {
	if len(data) < 4 {
		return LMI1Entry{}, errors.New("fdother: opaque-run cell is too short")
	}
	w := int(binary.LittleEndian.Uint16(data))
	h := int(binary.LittleEndian.Uint16(data[2:]))
	if w <= 0 || h <= 0 {
		return LMI1Entry{}, errors.New("fdother: opaque-run cell has empty dimensions")
	}
	pixels, err := decodeLMI1Pixels(data[4:], w*h)
	if err != nil {
		return LMI1Entry{}, err
	}
	return LMI1Entry{Width: w, Height: h, Pixels: pixels}, nil
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

// BlitAt copies an LMI1 cell with palette index zero preserving destination.
// It is used only by callers whose recovered drawing primitive has that
// rule; native 0x4e8af itself is opaque and uses BlitOpaqueAt below.
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

// BlitOpaqueAt reproduces 0x4e8af's direct decoded-pixel writes. In
// particular, palette index zero overwrites the destination.
func (e LMI1Entry) BlitOpaqueAt(dst []byte, stride, x, y int, mirror bool) error {
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
			dst[(y+row)*stride+x+col] = e.Pixels[row*e.Width+src]
		}
	}
	return nil
}

// BlitAtClipped is the explicit edge-clipped variant used by native slide
// callers whose cell begins outside the indexed viewport.  The strict
// BlitAt contract remains unchanged for ordinary UI assets.
func (e LMI1Entry) BlitAtClipped(dst []byte, stride, x, y int, mirror bool) error {
	if e.Width <= 0 || e.Height <= 0 || len(e.Pixels) != e.Width*e.Height {
		return errors.New("fdother: invalid LMI1 entry geometry")
	}
	if stride <= 0 || y >= len(dst)/stride || y+e.Height <= 0 {
		return errors.New("fdother: clipped LMI1 destination is outside surface")
	}
	for row := 0; row < e.Height; row++ {
		dy := y + row
		if dy < 0 || dy >= len(dst)/stride {
			continue
		}
		for col := 0; col < e.Width; col++ {
			dx := x + col
			if dx < 0 || dx >= stride {
				continue
			}
			src := col
			if mirror {
				src = e.Width - 1 - col
			}
			v := e.Pixels[row*e.Width+src]
			if v != 0 {
				dst[dy*stride+dx] = v
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
		//
		// 2026-08-16: some entries (confirmed for FDOTHER#14's church-menu
		// service icons, entries 3-10, 24x20 each) are stored as RAW
		// uncompressed pixel arrays, not RLE -- their directory slot is
		// exactly 4+w*h bytes, leaving zero room for compression. Running
		// these through decodeLMI1Pixels anyway "succeeds" (the RLE codec is
		// byte-general enough to consume any stream without erroring) but
		// produces garbage: raw pixel bytes above 0xc0 get misread as repeat
		// control bytes. That garbage was visually confirmed live (see
		// docs/knowledge-base/58-remake-live-verification-log.md, ch02
		// church_ch02) and root-caused by re-decoding these entries as raw
		// bytes instead, which produced clean, recognizable icon art. The
		// slot-size-matches-payload-size check below is a general detector
		// for this raw-storage case, not a special case for entries 3-10
		// specifically -- it also flagged resource #14 entry 2 (6x99) as raw
		// by the same signature, consistent with this being a real encoding
		// distinction in the format rather than a one-off.
		//
		// budget==w*h alone is ambiguous, not just a raw-storage signature:
		// it's also exactly what a genuinely-RLE-encoded entry looks like
		// when it happens to have zero compression benefit (e.g. a run
		// command costs 2 bytes regardless of run length, so a 2-pixel
		// single-run entry -- see TestParseLMI1NativeCodec's synthetic
		// {0xc2, 7} entry -- also has budget==w*h==2). Real icon art with any
		// flat color regions virtually never has *zero* RLE savings once
		// there are enough pixels for a run to pay for itself; only trust
		// the raw-storage signature above a size floor comfortably beyond
		// where that coincidence is plausible (confirmed cases are
		// 480/594 px; small synthetic/edge-case entries like the 2px test
		// stay on the RLE path as before).
		const lmi1RawDetectionMinPixels = 32
		var pixels []byte
		if budget := end - (off + 4); budget == w*h && w*h >= lmi1RawDetectionMinPixels {
			pixels = append([]byte(nil), data[off+4:off+4+w*h]...)
		} else {
			var err error
			pixels, err = decodeLMI1Pixels(data[off+4:], w*h)
			if err != nil {
				return nil, fmt.Errorf("fdother: LMI1 entry %d: %w", i, err)
			}
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
