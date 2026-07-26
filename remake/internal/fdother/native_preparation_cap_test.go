package fdother

import "testing"

func TestNativePreparationPartyLimitUsesNativeIndexBoundary(t *testing.T) {
	for _, tc := range []struct {
		index int
		want  int
	}{{-1, 15}, {0, 15}, {0x1a, 15}, {0x1b, 19}, {29, 19}} {
		if got := NativePreparationPartyLimit(tc.index); got != tc.want {
			t.Fatalf("limit(%d) = %d, want %d", tc.index, got, tc.want)
		}
	}
}
