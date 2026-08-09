package fdsave

import "testing"

func TestNativeBIOSKeyboardStateWordsDiffer(t *testing.T) {
	if (NativeBIOSKeyboardState{Word041A: 0x1234, Word041C: 0x1234}).WordsDiffer() {
		t.Fatal("equal raw words reported as different")
	}
	if !(NativeBIOSKeyboardState{Word041A: 0x1234, Word041C: 0x5678}).WordsDiffer() {
		t.Fatal("different raw words reported as equal")
	}
}

func TestNativeBIOSKeyboardStateCopyPreservesRawWordContract(t *testing.T) {
	s := NativeBIOSKeyboardState{Word041A: 0x1234, Word041C: 0x5678}
	if !s.Copy041ATo041C() {
		t.Fatal("different words did not report a write")
	}
	if s.Word041C != s.Word041A || s.WordsDiffer() {
		t.Fatalf("copy did not close raw words: %#v", s)
	}
	if s.Copy041ATo041C() {
		t.Fatal("equal words reported a second write")
	}
	var nilState *NativeBIOSKeyboardState
	if nilState.Copy041ATo041C() {
		t.Fatal("nil state accepted a raw write")
	}
}
