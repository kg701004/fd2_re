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

func TestNativeMapRangeModeRequiresExplicitRawBounds(t *testing.T) {
	st := &State{}
	if !st.MaterializeNativeMapRangeMode(0) ||
		!st.HasNativeMapRangeModeState || st.NativeMapRangeMode != 0 {
		t.Fatal("raw bootstrap range mode rejected")
	}
	if st.MaterializeNativeMapRangeMode(6) || st.NativeMapRangeMode != 0 {
		t.Fatal("out-of-range mode changed materialized state")
	}
}
