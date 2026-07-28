package main

import "testing"

func TestNativeBIOSFunctionScanRanges(t *testing.T) {
	tests := []struct {
		modifier int
		function int
		want     int
	}{
		{nativeFunctionShift, 1, 0x54},
		{nativeFunctionShift, 10, 0x5d},
		{nativeFunctionControl, 1, 0x5e},
		{nativeFunctionControl, 10, 0x67},
		{nativeFunctionAlt, 1, 0x68},
		{nativeFunctionAlt, 10, 0x71},
	}
	for _, test := range tests {
		got, ok := nativeBIOSFunctionScan(test.modifier, test.function)
		if !ok || got != test.want {
			t.Fatalf(
				"modifier=%d function=%d: got %#x,%v want %#x,true",
				test.modifier, test.function, got, ok, test.want,
			)
		}
	}
	for _, test := range [][2]int{{-1, 1}, {3, 1}, {0, 0}, {0, 11}} {
		if _, ok := nativeBIOSFunctionScan(test[0], test[1]); ok {
			t.Fatalf("invalid modifier/function %#v accepted", test)
		}
	}
}
