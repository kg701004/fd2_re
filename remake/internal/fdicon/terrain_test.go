package fdicon

import "testing"

func TestNativeTerrainFrameIndexMatches11EEE(t *testing.T) {
	cases := []struct {
		flags       byte
		flip, cycle int
		want        int
	}{
		{0x00, 1, 9, 100}, {0x04, 1, 9, 101}, {0x10, 1, 9, 104}, {0x08, 1, 9, 102},
		{0x1c, 1, 9, 102}, {0x10, 0, -3, 99},
	}
	for _, tc := range cases {
		got, err := NativeTerrainFrameIndex(100, tc.flags, tc.flip, tc.cycle)
		if err != nil || got != tc.want {
			t.Fatalf("%+v got=%d err=%v", tc, got, err)
		}
	}
	if _, err := NativeTerrainFrameIndex(0x400, 0, 0, 0); err == nil {
		t.Fatal("out-of-range tile accepted")
	}
	if _, err := NativeTerrainFrameIndex(0, 0, 2, 0); err == nil {
		t.Fatal("invalid flip accepted")
	}
}
