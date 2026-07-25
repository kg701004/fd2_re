// Package fdicon decodes FD2's 24×24 tactical-map unit sprites. It keeps
// indexed pixels and transparent spans separate so the native raw and LUT
// blitters (0x4deda / 0x4de56) can be reproduced without PNG conversion.
package fdicon

import (
	"encoding/binary"
	"errors"
	"fmt"
	"os"
)

const NativeSize = 24

type Bank struct{ Sprites []Sprite }

type Sprite struct{ Pixels, Mask []byte }

// SpriteFor implements the native 0x127e0 selector after 0x11019 has built
// its pointer table: group×12 + pose×3 + cycle. Pose is runtime +3; cycle is
// resolved from the global idle/moving counters, not directly from unit +4.
func (b *Bank) SpriteFor(group, pose, cycle int) (Sprite, error) {
	if b == nil || group < 0 || pose < 0 || pose >= 4 || cycle < 0 || cycle >= 3 {
		return Sprite{}, errors.New("fdicon: invalid native sprite selector")
	}
	i := group*12 + pose*3 + cycle
	if i < 0 || i >= len(b.Sprites) {
		return Sprite{}, errors.New("fdicon: sprite selector is out of bank")
	}
	return b.Sprites[i], nil
}

// NativeFrameIndex reproduces 0x127e0's cycle selector. motionOffset is the
// raw unit+4 movement offset: zero selects the idle counter, nonzero selects
// the moving counter. Native counters run 0..3 but map 3 back to frame 1;
// unit+0x26 forces the base frame regardless of either counter.
func NativeFrameIndex(motionOffset int, forceBase bool, idleCycle, movingCycle int) (int, error) {
	if idleCycle < 0 || idleCycle > 3 || movingCycle < 0 || movingCycle > 3 {
		return 0, errors.New("fdicon: invalid native cycle")
	}
	cycle := idleCycle
	if motionOffset != 0 {
		cycle = movingCycle
	}
	if cycle == 3 {
		cycle = 1
	}
	if forceBase {
		cycle = 0
	}
	return cycle, nil
}

func DecodeFile(path string) (*Bank, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(raw)
}

// Parse reads the FDICON.B24 header {u16 width,height,count; u32 offsets[]}.
func Parse(raw []byte) (*Bank, error) {
	if len(raw) < 6 {
		return nil, errors.New("fdicon: file is too short")
	}
	w, h, n := int(binary.LittleEndian.Uint16(raw)), int(binary.LittleEndian.Uint16(raw[2:])), int(binary.LittleEndian.Uint16(raw[4:]))
	if w != NativeSize || h != NativeSize || n == 0 || 6+n*4 > len(raw) {
		return nil, errors.New("fdicon: invalid header")
	}
	bank := &Bank{Sprites: make([]Sprite, n)}
	previous := 6 + n*4
	for i := range bank.Sprites {
		off := int(binary.LittleEndian.Uint32(raw[6+i*4:]))
		end := len(raw)
		if i+1 < n {
			end = int(binary.LittleEndian.Uint32(raw[6+(i+1)*4:]))
		}
		if off < previous || off >= end || end > len(raw) {
			return nil, fmt.Errorf("fdicon: invalid sprite %d offset", i)
		}
		pixels, mask, err := decode(raw[off:end])
		if err != nil {
			return nil, fmt.Errorf("fdicon: sprite %d: %w", i, err)
		}
		bank.Sprites[i] = Sprite{Pixels: pixels, Mask: mask}
		previous = off
	}
	return bank, nil
}

func decode(src []byte) ([]byte, []byte, error) {
	pixels, mask := make([]byte, NativeSize*NativeSize), make([]byte, NativeSize*NativeSize)
	p := 0
	for y := 0; y < NativeSize; y++ {
		x := 0
		for x < NativeSize {
			if p >= len(src) {
				return nil, nil, errors.New("RLE ends early")
			}
			c := src[p]
			p++
			count, mode := int(c&0x3f)+1, c>>6
			span := count
			if mode == 1 {
				span *= 2
			}
			if x+span > NativeSize {
				return nil, nil, errors.New("RLE overruns row")
			}
			write := func(at int, v byte) { pixels[y*NativeSize+at], mask[y*NativeSize+at] = v, 1 }
			switch mode {
			case 0:
				if p >= len(src) {
					return nil, nil, errors.New("run lacks value")
				}
				v := src[p]
				p++
				for i := 0; i < count; i++ {
					write(x+i, v)
				}
			case 1:
				if p >= len(src) {
					return nil, nil, errors.New("dither lacks value")
				}
				v := src[p]
				p++
				for i := 0; i < count; i++ {
					write(x+2*i+1, v)
				}
			case 2:
				if p+count > len(src) {
					return nil, nil, errors.New("literal exceeds data")
				}
				for i, v := range src[p : p+count] {
					write(x+i, v)
				}
				p += count
			}
			x += span
		}
	}
	return pixels, mask, nil
}

// BlitAt is native 0x4deda: raw indexed RLE, preserving transparent spans.
func (s Sprite) BlitAt(dst []byte, stride, x, y int) error {
	return s.blit(dst, stride, x, y, false)
}

// BlitPaletteBand is native 0x4de56. It maps each opaque source index to
// (index & 7) + 0x18; it is not a general 256-byte LUT path.
func (s Sprite) BlitPaletteBand(dst []byte, stride, x, y int) error {
	return s.blit(dst, stride, x, y, true)
}

// BlitForNativeFlags mirrors 0x127e0's test of runtime unit+5 bit7: clear
// selects 0x4deda raw pixels, set selects 0x4de56's palette-band pixels.
func (s Sprite) BlitForNativeFlags(dst []byte, stride, x, y int, flags byte) error {
	return s.blit(dst, stride, x, y, flags&0x80 != 0)
}

func (s Sprite) blit(dst []byte, stride, x, y int, paletteBand bool) error {
	if len(s.Pixels) != NativeSize*NativeSize || len(s.Mask) != len(s.Pixels) || stride < x+NativeSize || x < 0 || y < 0 || y+NativeSize > len(dst)/stride {
		return errors.New("fdicon: invalid blit")
	}
	for row := 0; row < NativeSize; row++ {
		for col := 0; col < NativeSize; col++ {
			i := row*NativeSize + col
			if s.Mask[i] != 0 {
				v := s.Pixels[i]
				if paletteBand {
					v = (v & 7) + 0x18
				}
				dst[(y+row)*stride+x+col] = v
			}
		}
	}
	return nil
}
