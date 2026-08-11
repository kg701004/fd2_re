package battle

import "testing"

func TestNativeMapViewMaterializesSaveIdentity(t *testing.T) {
	st := &State{W: 24, H: 24}
	view := NativeMapViewState{
		CameraX: 1, CameraY: 13, CursorX: 8, CursorY: 17,
		VisibleCursorX: 7, VisibleCursorY: 4,
	}
	if err := st.MaterializeNativeMapViewState(view); err != nil {
		t.Fatal(err)
	}
	view.VisibleCursorX++
	if err := st.MaterializeNativeMapViewState(view); err == nil {
		t.Fatal("accepted broken cursor-camera identity")
	}
}

func TestNativeMapCursorMovesCameraAtRecoveredThresholds(t *testing.T) {
	st := &State{W: 30, H: 30}
	if err := st.MaterializeNativeMapViewState(NativeMapViewState{
		CameraX: 4, CameraY: 5, CursorX: 15, CursorY: 11,
		VisibleCursorX: 11, VisibleCursorY: 6,
	}); err != nil {
		t.Fatal(err)
	}
	if moved, ok := st.MoveNativeMapCursor(1, 0); !moved || !ok {
		t.Fatal("right move rejected")
	}
	if got := st.NativeMapViewState; got.CameraX != 5 || got.CursorX != 16 || got.VisibleCursorX != 11 {
		t.Fatalf("right camera-follow=%+v", got)
	}
	if moved, ok := st.MoveNativeMapCursor(0, 1); !moved || !ok {
		t.Fatal("down move rejected")
	}
	if got := st.NativeMapViewState; got.CameraY != 6 || got.CursorY != 12 || got.VisibleCursorY != 6 {
		t.Fatalf("down camera-follow=%+v", got)
	}
	st.NativeMapViewState = NativeMapViewState{
		CameraX: 4, CameraY: 5, CursorX: 5, CursorY: 6,
		VisibleCursorX: 1, VisibleCursorY: 1,
	}
	if moved, ok := st.MoveNativeMapCursor(-1, 0); !moved || !ok {
		t.Fatal("left move rejected")
	}
	if got := st.NativeMapViewState; got.CameraX != 3 || got.CursorX != 4 || got.VisibleCursorX != 1 {
		t.Fatalf("left camera-follow=%+v", got)
	}
	if moved, ok := st.MoveNativeMapCursor(0, -1); !moved || !ok {
		t.Fatal("up move rejected")
	}
	if got := st.NativeMapViewState; got.CameraY != 4 || got.CursorY != 5 || got.VisibleCursorY != 1 {
		t.Fatalf("up camera-follow=%+v", got)
	}
}

func TestNativeMapCursorFieldEdgeIsValidNoMove(t *testing.T) {
	st := &State{W: 13, H: 8}
	if err := st.MaterializeNativeMapViewState(NativeMapViewState{}); err != nil {
		t.Fatal(err)
	}
	if moved, ok := st.MoveNativeMapCursor(-1, 0); moved || !ok {
		t.Fatalf("edge move=%v ok=%v", moved, ok)
	}
	if _, ok := st.MoveNativeMapCursor(1, 1); ok {
		t.Fatal("accepted diagonal move")
	}
}

// TestNativeMapCursorScrollThresholdTracksWiderViewport proves
// NativeMapViewportCols/Rows actually changes the camera-follow deadzone --
// not just accepted and ignored -- by placing the cursor where the original
// fixed 13x8 viewport would scroll the camera but a wider 20-tile viewport
// must not (the cursor is still comfortably inside the wider view).
func TestNativeMapCursorScrollThresholdTracksWiderViewport(t *testing.T) {
	st := &State{W: 30, H: 30, NativeMapViewportCols: 20, NativeMapViewportRows: 8}
	if err := st.MaterializeNativeMapViewState(NativeMapViewState{
		CameraX: 0, CameraY: 0, CursorX: 11, CursorY: 0,
		VisibleCursorX: 11, VisibleCursorY: 0,
	}); err != nil {
		t.Fatal(err)
	}
	// VisibleCursorX=11 is past the original 13x8's right threshold (>10)
	// but well inside the wider 20-tile viewport's (>17): must not scroll.
	if moved, ok := st.MoveNativeMapCursor(1, 0); !moved || !ok {
		t.Fatal("right move rejected")
	}
	if got := st.NativeMapViewState; got.CameraX != 0 || got.VisibleCursorX != 12 {
		t.Fatalf("wider viewport scrolled early: camera=%d visible=%d, want camera=0 visible=12", got.CameraX, got.VisibleCursorX)
	}
}

func TestNativeMapRangeModePreservesFullRawSelectorBounds(t *testing.T) {
	st := &State{}
	if !st.MaterializeNativeMapRangeMode(0) ||
		!st.HasNativeMapRangeModeState || st.NativeMapRangeMode != 0 {
		t.Fatal("raw bootstrap range mode rejected")
	}
	for _, mode := range []int{6, 7, 9, 11, 0x101} {
		if !st.MaterializeNativeMapRangeMode(mode) || st.NativeMapRangeMode != mode {
			t.Fatalf("verified raw selector %d rejected", mode)
		}
	}
	if got := NativeMapOverlaySelectorFromRecordByte(9); got != 11 {
		t.Fatalf("record byte 9 selector=%d, want 11", got)
	}
	if st.MaterializeNativeMapRangeMode(0x102) || st.NativeMapRangeMode != 0x101 {
		t.Fatal("out-of-range mode changed materialized state")
	}
}
