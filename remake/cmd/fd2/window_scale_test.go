package main

import "testing"

// TestWindowScaleForPicks1080pFriendlyDefault is the concrete case motivating
// this feature (重製目標 #2:「畫面升級到 1080P」): a standard 1920×1080
// monitor should default to 3x (1920×1200 logical-canvas-equivalent... no,
// 640*3=1920 fits exactly; 400*3=1200 exceeds 1080*0.9=972, so 3x must NOT
// fit and the picked scale must be 2x). This test exists specifically to
// pin down that arithmetic instead of trusting it by inspection.
func TestWindowScaleForPicks1080pFriendlyDefault(t *testing.T) {
	got := windowScaleFor(1920, 1080)
	// 640*2=1280<=1728, 400*2=800<=972 (2x fits); 640*3=1920<=1728 is FALSE
	// (1920 > 1728), so 3x does not fit within the 0.9 margin. Want 2x.
	if got != 2 {
		t.Fatalf("windowScaleFor(1920,1080) = %d, want 2 (3x's 1920 width exceeds the 0.9 margin of 1728)", got)
	}
}

func TestWindowScaleForPicksLargerScaleOnBiggerMonitor(t *testing.T) {
	// A 2560x1440 monitor has plenty of headroom for 3x (1920x1200 <=
	// 2304x1296) but not 4x (2560x1600 > 2304x1296).
	if got := windowScaleFor(2560, 1440); got != 3 {
		t.Fatalf("windowScaleFor(2560,1440) = %d, want 3", got)
	}
}

func TestWindowScaleForFallsBackToTwoWhenScreenSizeUnknown(t *testing.T) {
	for _, size := range [][2]int{{0, 0}, {-1, 1080}, {1920, 0}} {
		if got := windowScaleFor(size[0], size[1]); got != 2 {
			t.Errorf("windowScaleFor(%d,%d) = %d, want fallback 2", size[0], size[1], got)
		}
	}
}

func TestWindowScaleForNeverGoesBelowTwoOnATinyScreen(t *testing.T) {
	// Even a screen smaller than the 2x default (e.g. a small laptop panel)
	// must not shrink the window below the existing 1280x800 floor.
	if got := windowScaleFor(1024, 768); got != 2 {
		t.Fatalf("windowScaleFor(1024,768) = %d, want floor of 2 (must not shrink below the pre-existing default)", got)
	}
}
