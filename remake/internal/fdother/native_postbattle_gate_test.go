package fdother

import "testing"

func TestResolveNativePostbattleRoutePreservesHubAndPreparationBranches(t *testing.T) {
	table := make([]byte, 30)
	table[22], table[27] = 1, 1
	checks := []struct {
		chapter int
		option  byte
		callee  uint32
		prep    bool
	}{
		{0, 0, 0x2fc85, false},
		{0, 1, 0x2e341, false},
		{0, 3, 0x2e341, false},
		{0, 4, 0x3072f, false},
		{0, 2, 0x318ad, true},
		{22, 0, 0x318ad, true},
		{27, 4, 0x318ad, true},
	}
	for _, tc := range checks {
		got, ok := ResolveNativePostbattleRoute(tc.chapter, table, tc.option)
		if !ok || got.Callee != tc.callee || got.Preparation != tc.prep || got.Selector != tc.option {
			t.Fatalf("route(%d,%d) = %#v,%v; want callee=%#x prep=%v", tc.chapter, tc.option, got, ok, tc.callee, tc.prep)
		}
	}
	for _, tc := range []struct {
		chapter int
		option  byte
	}{{-1, 0}, {30, 0}, {0, 5}} {
		if got, ok := ResolveNativePostbattleRoute(tc.chapter, table, tc.option); ok || got != (NativePostbattleRoute{}) {
			t.Fatalf("invalid route(%d,%d) accepted: %#v,%v", tc.chapter, tc.option, got, ok)
		}
	}
}
