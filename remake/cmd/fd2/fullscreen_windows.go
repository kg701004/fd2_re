//go:build windows

package main

import "syscall"

// truePhysicalScreenSize returns the primary monitor's real physical pixel
// size. ebiten.SetFullscreen (and its Layout outsideW/outsideH) reports the
// DPI-virtualized monitor video mode on Windows when the desktop scale is
// not 100% (e.g. 1706x1066 instead of the real 2560x1600 at 150% scaling),
// which under-fills the real screen with an integer-scale letterbox. Ebiten
// already marks the whole process DPI-aware during its own startup (see
// goglfw/win32init_windows.go), so a direct GetSystemMetrics call made after
// that point returns true physical pixels.
func truePhysicalScreenSize() (int, int, bool) {
	user32 := syscall.NewLazyDLL("user32.dll")
	getSystemMetrics := user32.NewProc("GetSystemMetrics")
	const smCXScreen, smCYScreen = 0, 1
	w, _, _ := getSystemMetrics.Call(uintptr(smCXScreen))
	h, _, _ := getSystemMetrics.Call(uintptr(smCYScreen))
	if w <= 0 || h <= 0 {
		return 0, 0, false
	}
	return int(w), int(h), true
}
