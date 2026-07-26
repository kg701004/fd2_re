package fdother

import "fmt"

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
