package indexedmap

import "testing"

// TestNativeMapViewportReconstructsOriginalGeometry proves the new
// parametric border-math formula exactly reproduces every literal constant
// ComposeFrame/ComposeNativeFrame used before this type existed, at the
// original {13,8} window, before any call site is changed to use it.
func TestNativeMapViewportReconstructsOriginalGeometry(t *testing.T) {
	v := DefaultNativeMapViewport
	if v.Cols != 13 || v.Rows != 8 {
		t.Fatalf("DefaultNativeMapViewport = %+v, want {13,8}", v)
	}
	if got := v.contentWidth(); got != steadyViewportWidth {
		t.Errorf("contentWidth() = %d, want steadyViewportWidth %d", got, steadyViewportWidth)
	}
	if got := v.contentHeight(); got != viewHeight {
		t.Errorf("contentHeight() = %d, want viewHeight %d", got, viewHeight)
	}
	if got := v.canvasWidth(); got != viewWidth {
		t.Errorf("canvasWidth() = %d, want viewWidth %d", got, viewWidth)
	}
	if got := v.canvasHeight(); got != 200 {
		t.Errorf("canvasHeight() = %d, want 200", got)
	}
	if got := v.vgaSize(); got != NativeMapVGASize {
		t.Errorf("vgaSize() = %d, want NativeMapVGASize %d", got, NativeMapVGASize)
	}
	if got := v.viewportOffset(); got != steadyViewportOffset {
		t.Errorf("viewportOffset() = %#x, want steadyViewportOffset %#x", got, steadyViewportOffset)
	}
	if got := v.workStride(); got != workStride {
		t.Errorf("workStride() = %d, want package workStride %d", got, workStride)
	}
	if got := v.workHeight(); got != NativeUnitPresentWorkSize/workStride {
		t.Errorf("workHeight() = %d, want %d", got, NativeUnitPresentWorkSize/workStride)
	}
	if got := v.workSize(); got != NativeUnitPresentWorkSize {
		t.Errorf("workSize() = %#x, want NativeUnitPresentWorkSize %#x", got, NativeUnitPresentWorkSize)
	}
	if got := v.workBase(); got != workBase {
		t.Errorf("workBase() = %#x, want package workBase %#x", got, workBase)
	}
}

// TestNativeMapViewportWiderPreset sanity-checks the formula stays
// self-consistent (border preserved, no negative/zero sizes) for a wider,
// remake-only preset.
func TestNativeMapViewportWiderPreset(t *testing.T) {
	v := NativeMapViewport{Cols: 20, Rows: 12}
	if got, want := v.contentWidth(), 480; got != want {
		t.Errorf("contentWidth() = %d, want %d", got, want)
	}
	if got, want := v.contentHeight(), 288; got != want {
		t.Errorf("contentHeight() = %d, want %d", got, want)
	}
	if got, want := v.canvasWidth(), 488; got != want {
		t.Errorf("canvasWidth() = %d, want %d", got, want)
	}
	if got, want := v.canvasHeight(), 296; got != want {
		t.Errorf("canvasHeight() = %d, want %d", got, want)
	}
	if got, want := v.viewportOffset(), 4*488+4; got != want {
		t.Errorf("viewportOffset() = %d, want %d", got, want)
	}
	if got, want := v.workStride(), 480+2*72; got != want {
		t.Errorf("workStride() = %d, want %d", got, want)
	}
	if got, want := v.workHeight(), 288+2*72; got != want {
		t.Errorf("workHeight() = %d, want %d", got, want)
	}
	if got, want := v.workBase(), 72*(480+2*72)+72; got != want {
		t.Errorf("workBase() = %d, want %d", got, want)
	}
}
