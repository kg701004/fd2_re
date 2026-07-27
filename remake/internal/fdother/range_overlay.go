package fdother

import (
	"encoding/binary"
	"errors"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
)

const (
	nativeRangeOverlayResource = 1
	nativeRangeOverlayStride   = 0x1c8
	nativeRangeOverlayBase     = 0x8088
	nativeRangeOverlayTiles    = 20
)

// NativeRangeOverlayPlacement is one direct 0x126f7 invocation emitted by
// 0x122dc. Descriptor is the caller's raw descriptor-bank index; it is not a
// gameplay range class or a GUI highlight colour.
type NativeRangeOverlayPlacement struct {
	X, Y       int
	Descriptor int
}

type nativeRangeOverlayOffset struct {
	dx, dy     int
	descriptor int
}

// NativeRangeOverlayPlacements materializes the exact ordered 0x122dc calls
// for raw modes 1..5 around cursorX/cursorY.  Multiple calls to the same
// coordinate are retained because native uses different descriptors there.
//
// Mode 6 has no 0x126f7 calls: it instead clears a byte at
// [0x53a51 + 4*(cursorX + cursorY*[0x53ac1]) + 7].  It is intentionally
// rejected here so a renderer cannot mistake that grid mutation for a draw.
func NativeRangeOverlayPlacements(mode, cursorX, cursorY int) ([]NativeRangeOverlayPlacement, error) {
	offsets, ok := nativeRangeOverlayModes[mode]
	if !ok {
		return nil, fmt.Errorf("fdother: native range overlay mode %d has no drawable placement table", mode)
	}
	placements := make([]NativeRangeOverlayPlacement, len(offsets))
	for i, offset := range offsets {
		placements[i] = NativeRangeOverlayPlacement{
			X:          cursorX + offset.dx,
			Y:          cursorY + offset.dy,
			Descriptor: offset.descriptor,
		}
	}
	return placements, nil
}

// NativeRangeOverlayMode6ByteAddress is mode 6's raw address expression.
// gridBase and record storage are deliberately absent: this returns the
// byte offset from [0x53a51] only, and callers must establish that native
// memory layout before writing.  width must be positive; native itself does
// not protect the coordinate arithmetic.
func NativeRangeOverlayMode6ByteAddress(width, cursorX, cursorY int) (int, error) {
	if width <= 0 {
		return 0, fmt.Errorf("fdother: native range overlay mode 6 width must be positive")
	}
	return 4*(cursorX+cursorY*width) + 7, nil
}

// ClearNativeRangeOverlayMode6FieldByte applies mode 6 to a raw FDFIELD
// composition resource.  0x108f0..0x10932 loads that resource to [0x53a51],
// whose signed u16 header is width/height followed by four bytes per cell;
// 0x4dbfc initializes the fourth byte (event high byte / raw blit-mode byte)
// to 0xff.  Mode 6's [base + 4*(x+y*width) + 7] write is therefore exactly
// the fourth byte of the selected cell, not a range-overlay sprite operation.
// No higher gameplay meaning is assigned to clearing that byte.
func ClearNativeRangeOverlayMode6FieldByte(field []byte, cursorX, cursorY int) error {
	if len(field) < 4 {
		return errors.New("fdother: native range overlay mode 6 field is too short")
	}
	width := int(int16(binary.LittleEndian.Uint16(field)))
	height := int(int16(binary.LittleEndian.Uint16(field[2:])))
	if width <= 0 || height <= 0 || cursorX < 0 || cursorX >= width || cursorY < 0 || cursorY >= height || width > (len(field)-4)/4/height {
		return errors.New("fdother: invalid native range overlay mode 6 field coordinate")
	}
	offset, err := NativeRangeOverlayMode6ByteAddress(width, cursorX, cursorY)
	if err != nil {
		return err
	}
	if offset >= len(field) {
		return errors.New("fdother: native range overlay mode 6 field is truncated")
	}
	field[offset] = 0
	return nil
}

// DecodeNativeRangeOverlayBank reads the exact FDOTHER #1 resource loaded to
// [0x53a4d] at 0x25c7d..0x25c92.  Its {24,24,20,u32 offsets[]} header is the
// same four-mode RLE bank ABI as FDICON.B24; only descriptors 0..18 are used
// by 0x122dc's modes 1..5.  Requiring the observed 20 entries prevents a
// partial editable asset from silently changing the native descriptor table.
func DecodeNativeRangeOverlayBank(datPath string) (*fdicon.Bank, error) {
	raw, err := ReadResource(datPath, nativeRangeOverlayResource)
	if err != nil {
		return nil, err
	}
	bank, err := fdicon.Parse(raw)
	if err != nil {
		return nil, fmt.Errorf("fdother: native range overlay bank: %w", err)
	}
	if len(bank.Sprites) != nativeRangeOverlayTiles {
		return nil, fmt.Errorf("fdother: native range overlay has %d descriptors, want %d", len(bank.Sprites), nativeRangeOverlayTiles)
	}
	return bank, nil
}

// BlitNativeRangeOverlay executes the verified drawable part of 0x122dc and
// 0x126f7 against the native 456-stride work buffer.  The descriptor cells
// are direct 0x4deda RLE input, so Sprite.BlitAt deliberately preserves
// mode-3 spans.  Camera clipping happens before descriptor lookup exactly as
// in 0x126f7. Raw mode 0 follows 0x122dc's default no-op branch. Mode 6
// remains rejected because it is a separate raw grid mutation, not a drawing
// operation.
//
// All selected visible sprites and their destinations are preflighted before
// writing. This is the editable-input safety boundary, not a claim that the
// original performed bounds checks on its framebuffer pointer.
func BlitNativeRangeOverlay(bank *fdicon.Bank, dst []byte, cameraX, cameraY, visibleWidth, visibleHeight, mode, cursorX, cursorY int) error {
	if bank == nil || len(bank.Sprites) != nativeRangeOverlayTiles {
		return errors.New("fdother: incomplete native range overlay descriptor bank")
	}
	if visibleWidth <= 0 || visibleHeight <= 0 || len(dst)%nativeRangeOverlayStride != 0 {
		return errors.New("fdother: invalid native range overlay framebuffer")
	}
	if mode == 0 {
		return nil
	}
	placements, err := NativeRangeOverlayPlacements(mode, cursorX, cursorY)
	if err != nil {
		return err
	}
	type blit struct{ x, y, descriptor int }
	visible := make([]blit, 0, len(placements))
	for _, placement := range placements {
		if placement.X < cameraX || placement.X >= cameraX+visibleWidth || placement.Y < cameraY || placement.Y >= cameraY+visibleHeight {
			continue
		}
		if placement.Descriptor < 0 || placement.Descriptor >= len(bank.Sprites) {
			return errors.New("fdother: native range overlay descriptor is outside bank")
		}
		x := nativeRangeOverlayBase%nativeRangeOverlayStride + (placement.X-cameraX)*fdicon.NativeSize
		y := nativeRangeOverlayBase/nativeRangeOverlayStride + (placement.Y-cameraY)*fdicon.NativeSize
		if x < 0 || y < 0 || x+fdicon.NativeSize > nativeRangeOverlayStride || y+fdicon.NativeSize > len(dst)/nativeRangeOverlayStride {
			return errors.New("fdother: native range overlay destination is outside framebuffer")
		}
		visible = append(visible, blit{x, y, placement.Descriptor})
	}
	for _, draw := range visible {
		if err := bank.Sprites[draw.descriptor].BlitAt(dst, nativeRangeOverlayStride, draw.x, draw.y); err != nil {
			return fmt.Errorf("fdother: native range overlay descriptor %d: %w", draw.descriptor, err)
		}
	}
	return nil
}

// The literals below are transcribed in call order from 0x122dc..0x126f6.
// Keep this as a call table rather than normalizing into an inferred shape.
var nativeRangeOverlayModes = map[int][]nativeRangeOverlayOffset{
	1: {{0, 0, 0}},
	2: {{0, 0, 1}},
	3: {
		{0, 0, 14}, {0, -1, 2}, {-1, 0, 3}, {1, 0, 4}, {0, 1, 5},
	},
	4: {
		{0, 0, 1}, {0, -2, 2}, {-2, 0, 3}, {2, 0, 4}, {0, 2, 5},
		{-1, -1, 6}, {1, -1, 7}, {-1, 1, 8}, {1, 1, 9},
		{0, -1, 10}, {-1, 0, 11}, {1, 0, 12}, {0, 1, 13},
	},
	5: {
		{0, 0, 1}, {0, -3, 2}, {-3, 0, 3}, {3, 0, 4}, {0, 3, 5},
		{-1, -2, 6}, {-2, -1, 6}, {1, -2, 7}, {-2, 2, 7},
		{1, 2, 8}, {1, -2, 8}, {2, 2, 9}, {1, 2, 9},
		{0, -2, 10}, {-2, 0, 11}, {2, 0, 12}, {0, 2, 13},
		{-1, -1, 15}, {1, -1, 16}, {-1, 1, 17}, {1, 1, 18},
	},
}
