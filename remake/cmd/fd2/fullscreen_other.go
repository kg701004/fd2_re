//go:build !windows

package main

// truePhysicalScreenSize has no non-Windows implementation; callers fall
// back to ebiten.SetFullscreen's own (correct on other platforms) monitor
// size detection.
func truePhysicalScreenSize() (int, int, bool) {
	return 0, 0, false
}
