package fdother

import "testing"

func TestNativeTerrainLUTIndexMatches51A97(t *testing.T) {
	want := []int{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1}
	for phase, expected := range want {
		got, err := NativeTerrainLUTIndex(phase)
		if err != nil || got != expected {
			t.Fatalf("phase=%d got=%d err=%v", phase, got, err)
		}
	}
	if _, err := NativeTerrainLUTIndex(-1); err == nil {
		t.Fatal("negative phase accepted")
	}
	if _, err := NativeTerrainLUTIndex(20); err == nil {
		t.Fatal("out-of-range phase accepted")
	}
}
