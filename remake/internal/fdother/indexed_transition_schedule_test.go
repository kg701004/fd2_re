package fdother

import "testing"

func TestBuildNativeIndexedTransitionSchedulePreservesRawLoop(t *testing.T) {
	s, err := BuildNativeIndexedTransitionSchedule(10, 8)
	if err != nil {
		t.Fatal(err)
	}
	if len(s.Frames) != 9 || s.Frames[0].LUTIndex != 9 || s.Frames[8].LUTIndex != 1 {
		t.Fatalf("frames=%#v", s.Frames)
	}
	if s.Frames[0].Radius != 10 || s.Frames[8].Radius != 74 || s.TailDelayMs != 500 {
		t.Fatalf("radius/tail frames=%#v tail=%d", s.Frames, s.TailDelayMs)
	}
	if len(s.PaletteDeltas) != 32 || s.PaletteDeltas[0] != 0 || s.PaletteDeltas[31] != 62 || s.PaletteDelayMs != 4 {
		t.Fatalf("palette=%v delay=%d", s.PaletteDeltas, s.PaletteDelayMs)
	}
}

func TestBuildNativeIndexedTransitionScheduleRejectsInvalidRadius(t *testing.T) {
	if _, err := BuildNativeIndexedTransitionSchedule(-1, 0); err == nil {
		t.Fatal("negative radius unexpectedly accepted")
	}
	if _, err := BuildNativeIndexedTransitionSchedule(1, 0x8000); err == nil {
		t.Fatal("oversized radius step unexpectedly accepted")
	}
}
