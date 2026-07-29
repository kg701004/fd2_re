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
		direct  bool
	}{
		{0, 0, 0x2fc85, false, false},
		{0, 1, 0x2e341, false, false},
		{0, 3, 0x2e341, false, false},
		{0, 4, 0x3072f, false, false},
		{0, 2, 0x318ad, true, false},
		{22, 0, 0x318ad, true, true},
		{27, 4, 0x318ad, true, true},
	}
	for _, tc := range checks {
		got, ok := ResolveNativePostbattleRoute(tc.chapter, table, tc.option)
		if !ok || got.Callee != tc.callee ||
			got.Preparation != tc.prep ||
			got.DirectPreparation != tc.direct ||
			got.Selector != tc.option {
			t.Fatalf(
				"route(%d,%d) = %#v,%v; want callee=%#x prep=%v direct=%v",
				tc.chapter, tc.option, got, ok, tc.callee, tc.prep, tc.direct,
			)
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

func TestResolveNativePostbattleOutcomePreservesLoopAndRawReturns(t *testing.T) {
	table := make([]byte, 30)
	table[22] = 1
	checks := []struct {
		chapter      int
		selector     byte
		calleeResult int
		repeat       bool
		returnValue  int
	}{
		{22, 4, 0, true, 0},
		{22, 4, 1, false, 0},
		{0, 2, 0, true, 0},
		{0, 2, 1, false, 0},
		{0, 0, 0, true, 0},
		{0, 0, 1, false, 1},
		{0, 1, -1, false, 1},
		{0, 3, 7, false, 1},
		{0, 4, 1, false, 1},
	}
	for _, tc := range checks {
		route, ok := ResolveNativePostbattleRoute(
			tc.chapter, table, tc.selector,
		)
		if !ok {
			t.Fatalf("route(%d,%d) unavailable", tc.chapter, tc.selector)
		}
		got, ok := ResolveNativePostbattleOutcome(route, tc.calleeResult)
		if !ok || got.Repeat != tc.repeat ||
			got.ReturnValue != tc.returnValue {
			t.Fatalf(
				"outcome(%d,%d,%d) = %#v,%v; want repeat=%v return=%d",
				tc.chapter, tc.selector, tc.calleeResult, got, ok,
				tc.repeat, tc.returnValue,
			)
		}
	}
}

func TestResolveNativePostbattleOutcomeRejectsInventedRoutes(t *testing.T) {
	bad := []NativePostbattleRoute{
		{},
		{Selector: 0, Callee: 0x318ad},
		{Selector: 2, Callee: 0x318ad},
		{
			Selector:          0,
			Callee:            0x2fc85,
			DirectPreparation: true,
		},
	}
	for _, route := range bad {
		if got, ok := ResolveNativePostbattleOutcome(route, 1); ok {
			t.Fatalf("invented route %#v accepted as %#v", route, got)
		}
	}
}
