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

// BattleActionOverlayState constructs the state passed by the native battle
// action wrapper 0x18d8c. Its direction states are a fixed [0,1,2,3], so an
// enabled action selects cells [0,2,4,6] and a disabled action selects
// [3,5,7,9]. Other 0x1741c callers (such as 0x1728c) use separate state
// tables and must construct ActionOverlayState explicitly.
func BattleActionOverlayState(availability [4]int) ActionOverlayState {
	return ActionOverlayState{
		Availability:   availability,
		DirectionState: [4]int{0, 1, 2, 3},
	}
}

const (
	nativeFramebufferStride = 0x1c8
	nativeActionOverlayBase = 0x8088
	nativeActionOverlayStep = 0x18

	// NativeActionOverlaySnapshotWidth/Height and Bytes are the exact private
	// indexed backup size used by 0x175a9/0x17643.  The caller must provide the
	// top-left rectangle explicitly; this package does not infer a screen
	// anchor from the cursor or from the relative blit offsets.
	NativeActionOverlaySnapshotWidth  = 72
	NativeActionOverlaySnapshotHeight = 72
	NativeActionOverlaySnapshotBytes  = NativeActionOverlaySnapshotWidth * NativeActionOverlaySnapshotHeight
)

// validateActionOverlaySnapshotRect checks a caller-owned indexed framebuffer
// rectangle without assigning any unproven coordinate meaning to it.
func validateActionOverlaySnapshotRect(buf []byte, stride, x, y int) error {
	if stride < NativeActionOverlaySnapshotWidth || x < 0 || y < 0 ||
		x+NativeActionOverlaySnapshotWidth > stride ||
		y+NativeActionOverlaySnapshotHeight > len(buf)/stride {
		return errors.New("fdother: action overlay snapshot rectangle is invalid")
	}
	return nil
}

// CaptureActionOverlaySnapshot copies the native 72×72 indexed backup region.
// x and y are the explicit top-left rectangle supplied by the caller.  No
// cursor, camera, palette, or screen-coordinate semantics are inferred here.
func CaptureActionOverlaySnapshot(src []byte, stride, x, y int) ([]byte, error) {
	if stride <= 0 || len(src) == 0 {
		return nil, errors.New("fdother: action overlay snapshot source is invalid")
	}
	if err := validateActionOverlaySnapshotRect(src, stride, x, y); err != nil {
		return nil, err
	}
	snapshot := make([]byte, NativeActionOverlaySnapshotBytes)
	for row := 0; row < NativeActionOverlaySnapshotHeight; row++ {
		copy(
			snapshot[row*NativeActionOverlaySnapshotWidth:],
			src[(y+row)*stride+x:(y+row)*stride+x+NativeActionOverlaySnapshotWidth],
		)
	}
	return snapshot, nil
}

// RestoreActionOverlaySnapshot restores a previously captured native 72×72
// indexed rectangle.  A malformed snapshot is rejected before any write.
func RestoreActionOverlaySnapshot(dst, snapshot []byte, stride, x, y int) error {
	if stride <= 0 || len(dst) == 0 || len(snapshot) != NativeActionOverlaySnapshotBytes {
		return errors.New("fdother: action overlay snapshot restore input is invalid")
	}
	if err := validateActionOverlaySnapshotRect(dst, stride, x, y); err != nil {
		return err
	}
	for row := 0; row < NativeActionOverlaySnapshotHeight; row++ {
		copy(
			dst[(y+row)*stride+x:(y+row)*stride+x+NativeActionOverlaySnapshotWidth],
			snapshot[row*NativeActionOverlaySnapshotWidth:],
		)
	}
	return nil
}

// ActionOverlayOrigin implements the common 0x1741c/0x179d5 framebuffer
// address expression. cursorColumn and cursorRow are the visible map cursor
// coordinates; the separately tracked camera scroll globals are not used.
func ActionOverlayOrigin(cursorColumn, cursorRow int) (int, error) {
	if cursorColumn < 0 || cursorRow < 0 {
		return 0, errors.New("fdother: negative action overlay origin")
	}
	return nativeActionOverlayBase + nativeActionOverlayStep*cursorColumn + nativeActionOverlayStep*nativeFramebufferStride*cursorRow, nil
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
