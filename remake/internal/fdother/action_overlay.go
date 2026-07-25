package fdother

import (
	"errors"
	"fmt"
)

// ActionOverlayState is the native cell-selection state for the four action
// directions, in native order: up, left, right, down. The values intentionally
// remain raw: their gameplay/icon meaning is not yet recovered.
type ActionOverlayState struct {
	Availability   [4]int
	DirectionState [4]int
}

const (
	nativeFramebufferStride = 0x1c8
	nativeActionOverlayBase = 0x8088
	nativeActionOverlayStep = 0x18
)

// ActionOverlayOrigin implements the common 0x1741c/0x179d5 framebuffer
// address expression. column and row are deliberately raw source values;
// their originating globals' gameplay meaning is not yet recovered.
func ActionOverlayOrigin(column, row int) (int, error) {
	if column < 0 || row < 0 {
		return 0, errors.New("fdother: negative action overlay origin")
	}
	return nativeActionOverlayBase + nativeActionOverlayStep*column + nativeActionOverlayStep*nativeFramebufferStride*row, nil
}

// CellIndex implements the FD2.EXE 0x1741c table ABI:
//
//	index = 3*availabilityWord + 2*directionState
//
// The returned index addresses an FDOTHER #2 raw cell. It does not infer a
// direction's visible icon or availability semantics.
func (s ActionOverlayState) CellIndex(direction int) (int, error) {
	if direction < 0 || direction >= len(s.Availability) {
		return 0, fmt.Errorf("fdother: action overlay direction %d is invalid", direction)
	}
	availability := s.Availability[direction]
	directionState := s.DirectionState[direction]
	if availability < 0 || directionState < 0 {
		return 0, fmt.Errorf("fdother: negative action overlay state for direction %d", direction)
	}
	return 3*availability + 2*directionState, nil
}

// ActionOverlayFrameOffsets returns the four byte offsets used by native
// 0x1741c/0x176b4 for an opening or closing animation frame. They are offsets
// into a framebuffer with native stride 0x1c8; callers supply the concrete
// origin. No screen anchor is implied here because it remains unproven.
func ActionOverlayFrameOffsets(frame int, closing bool) ([4]int, error) {
	if frame < 0 || frame >= 4 {
		return [4]int{}, fmt.Errorf("fdother: action overlay frame %d is invalid", frame)
	}
	if closing {
		// 0x176b4 has an independently initialized close sequence; it is
		// not the opening frames in reverse order.
		start := [4]int{-0x23a0, 0x378, 0x3a8, 0x2ac0}
		delta := [4]int{0x8e8, 6, -6, -0x8e8}
		var offsets [4]int
		for direction := range offsets {
			offsets[direction] = start[direction] + frame*delta[direction]
		}
		return offsets, nil
	}
	delta := [4]int{-0x8e8, -6, 6, 0x8e8}
	var offsets [4]int
	for direction := range offsets {
		offsets[direction] = 0x390 + frame*delta[direction]
	}
	return offsets, nil
}

// BlitActionOverlayFrame applies one native animation frame of the four raw
// FDOTHER #2 cells. origin is a byte address, rather than an inferred x/y
// anchor; offsets are then converted using the caller's framebuffer stride.
func BlitActionOverlayFrame(cells []RawCell, state ActionOverlayState, dst []byte, stride, origin, frame int, closing bool) error {
	if stride <= 0 || origin < 0 || origin >= len(dst) {
		return fmt.Errorf("fdother: action overlay origin is invalid")
	}
	offsets, err := ActionOverlayFrameOffsets(frame, closing)
	if err != nil {
		return err
	}
	for direction, offset := range offsets {
		index, err := state.CellIndex(direction)
		if err != nil {
			return err
		}
		if index >= len(cells) {
			return fmt.Errorf("fdother: action overlay cell %d is absent", index)
		}
		pos := origin + offset
		if pos < 0 || pos >= len(dst) {
			return fmt.Errorf("fdother: action overlay position %d is invalid", pos)
		}
		if err := cells[index].BlitAt(dst, stride, pos%stride, pos/stride); err != nil {
			return fmt.Errorf("fdother: action overlay direction %d: %w", direction, err)
		}
	}
	return nil
}
