package main

import (
	"github.com/hajimehoshi/ebiten/v2"
	"github.com/hajimehoshi/ebiten/v2/inpututil"
)

const (
	nativeFunctionShift = iota
	nativeFunctionControl
	nativeFunctionAlt
)

func nativeBIOSFunctionScan(modifier, function int) (int, bool) {
	if modifier < nativeFunctionShift || modifier > nativeFunctionAlt ||
		function < 1 || function > 10 {
		return 0, false
	}
	return [...]int{0x54, 0x5e, 0x68}[modifier] + function - 1, true
}

func nativeModifierHeld() bool {
	return ebiten.IsKeyPressed(ebiten.KeyShift) ||
		ebiten.IsKeyPressed(ebiten.KeyControl) ||
		ebiten.IsKeyPressed(ebiten.KeyAlt)
}

func pressedNativeTownSecretScan() (int, bool) {
	modifier := -1
	for index, key := range []ebiten.Key{
		ebiten.KeyShift, ebiten.KeyControl, ebiten.KeyAlt,
	} {
		if ebiten.IsKeyPressed(key) {
			if modifier != -1 {
				return 0, false
			}
			modifier = index
		}
	}
	if modifier == -1 {
		return 0, false
	}
	for index, key := range []ebiten.Key{
		ebiten.KeyF1, ebiten.KeyF2, ebiten.KeyF3, ebiten.KeyF4, ebiten.KeyF5,
		ebiten.KeyF6, ebiten.KeyF7, ebiten.KeyF8, ebiten.KeyF9, ebiten.KeyF10,
	} {
		if inpututil.IsKeyJustPressed(key) {
			return nativeBIOSFunctionScan(modifier, index+1)
		}
	}
	return 0, false
}
