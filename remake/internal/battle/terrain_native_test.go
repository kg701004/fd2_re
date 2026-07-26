package battle

import "testing"

func TestNativeTerrainAPDPPct(t *testing.T) {
	cases := []struct {
		code     byte
		ap, dp   int
		accepted bool
	}{
		{0, 5, 0, true},
		{1, 0, 0, true},
		{2, -5, 10, true},
		{3, -5, 10, true},
		{4, -5, -5, true},
		{5, 0, 0, true},
		{6, 0, 0, false},
	}
	for _, tc := range cases {
		ap, dp, ok := NativeTerrainAPDPPct(tc.code)
		if ap != tc.ap || dp != tc.dp || ok != tc.accepted {
			t.Errorf("code %d = (%d,%d,%v), want (%d,%d,%v)", tc.code, ap, dp, ok, tc.ap, tc.dp, tc.accepted)
		}
	}
}

func TestTerrainAPDPPct_PrefersValidatedNativeCellCode(t *testing.T) {
	st := &State{
		W:                      3,
		H:                      2,
		Cost:                   []int{1, 1, 1, 1, 1, 1},
		NativeTerrainMoveCodes: []byte{0, 1, 2, 3, 4, 5},
	}
	want := [][2]int{{5, 0}, {0, 0}, {-5, 10}, {-5, 10}, {-5, -5}, {0, 0}}
	for i, pair := range want {
		ap, dp := st.TerrainAPDPPct(i%st.W, i/st.W)
		if ap != pair[0] || dp != pair[1] {
			t.Errorf("cell %d = (%d,%d), want (%d,%d)", i, ap, dp, pair[0], pair[1])
		}
	}
}

func TestTerrainAPDPPct_IncompleteNativeCodesUseLegacyFallback(t *testing.T) {
	st := &State{W: 2, H: 1, Cost: []int{1, 2}, NativeTerrainMoveCodes: []byte{0}}
	if ap, dp := st.TerrainAPDPPct(0, 0); ap != 5 || dp != -5 {
		t.Errorf("legacy flat fallback = (%d,%d), want (5,-5)", ap, dp)
	}
	if ap, dp := st.TerrainAPDPPct(1, 0); ap != -5 || dp != -5 {
		t.Errorf("legacy swamp fallback = (%d,%d), want (-5,-5)", ap, dp)
	}
}
