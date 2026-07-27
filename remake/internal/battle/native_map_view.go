package battle

import "fmt"

const (
	nativeMapViewWidth  = 13
	nativeMapViewHeight = 8
)

// NativeMapViewState owns camera [0x53aa9/0x53aad], absolute cursor
// [0x53ab1/0x53ab5], and camera-relative visible cursor
// [0x53ab9/0x53abd].
type NativeMapViewState struct {
	CameraX, CameraY               int
	CursorX, CursorY               int
	VisibleCursorX, VisibleCursorY int
}

func validateNativeMapView(view NativeMapViewState, width, height int) error {
	if width < nativeMapViewWidth || height < nativeMapViewHeight ||
		view.CameraX < 0 || view.CameraX > width-nativeMapViewWidth ||
		view.CameraY < 0 || view.CameraY > height-nativeMapViewHeight ||
		view.CursorX < 0 || view.CursorX >= width ||
		view.CursorY < 0 || view.CursorY >= height ||
		view.VisibleCursorX != view.CursorX-view.CameraX ||
		view.VisibleCursorY != view.CursorY-view.CameraY {
		return fmt.Errorf("battle: native map view is outside field or violates cursor-camera identity")
	}
	return nil
}

func (s *State) MaterializeNativeMapViewState(view NativeMapViewState) error {
	if s == nil {
		return fmt.Errorf("battle: nil native map view state")
	}
	if err := validateNativeMapView(view, s.W, s.H); err != nil {
		return err
	}
	s.NativeMapViewState = view
	s.HasNativeMapViewState = true
	return nil
}

// MoveNativeMapCursor reproduces the four helpers at 0x11b48..0x11cac.
// moved is false at a field edge; ok is false for malformed state/input.
func (s *State) MoveNativeMapCursor(dx, dy int) (moved, ok bool) {
	if s == nil || !s.HasNativeMapViewState || absInt(dx)+absInt(dy) != 1 {
		return false, false
	}
	view := s.NativeMapViewState
	if err := validateNativeMapView(view, s.W, s.H); err != nil {
		return false, false
	}
	switch {
	case dy < 0:
		if view.CursorY == 0 {
			return false, true
		}
		view.CursorY--
		if view.VisibleCursorY < 2 && view.CameraY != 0 {
			view.CameraY--
		} else {
			view.VisibleCursorY--
		}
	case dy > 0:
		if view.CursorY == s.H-1 {
			return false, true
		}
		view.CursorY++
		if view.VisibleCursorY > 5 && view.CameraY != s.H-nativeMapViewHeight {
			view.CameraY++
		} else {
			view.VisibleCursorY++
		}
	case dx > 0:
		if view.CursorX == s.W-1 {
			return false, true
		}
		view.CursorX++
		if view.VisibleCursorX > 10 && view.CameraX != s.W-nativeMapViewWidth {
			view.CameraX++
		} else {
			view.VisibleCursorX++
		}
	case dx < 0:
		if view.CursorX == 0 {
			return false, true
		}
		view.CursorX--
		if view.VisibleCursorX < 2 && view.CameraX != 0 {
			view.CameraX--
		} else {
			view.VisibleCursorX--
		}
	}
	if err := validateNativeMapView(view, s.W, s.H); err != nil {
		return false, false
	}
	s.NativeMapViewState = view
	return true, true
}
