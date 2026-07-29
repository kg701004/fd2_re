package fdother

import (
	"reflect"
	"testing"
)

func TestPlanNativeUnitMode2DoesNotInventNearestTargetFallback(t *testing.T) {
	got := PlanNativeUnitMode2(false)
	want := []NativeUnitModeAction{
		NativeModeCall14EF0,
		NativeModeCall14237,
		NativeModeCall13FD4,
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 2 actions = %v, want %v", got, want)
	}
	if got := PlanNativeUnitMode2(true); !reflect.DeepEqual(
		got,
		[]NativeUnitModeAction{NativeModeCall14EF0},
	) {
		t.Fatalf("successful mode 2 actions = %v", got)
	}
}

func TestPlanNativeUnitMode11UsesIndependentSignedGates(t *testing.T) {
	got := PlanNativeUnitMode11(6, 5, false)
	want := []NativeUnitModeAction{
		NativeModeCall1598A,
		NativeModeCall15311,
		NativeModeCall14237,
		NativeModeCall14121,
		NativeModeCall13FD4,
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 11 command branch = %v, want %v", got, want)
	}

	got = PlanNativeUnitMode11(-1, 6, false)
	want = []NativeUnitModeAction{
		NativeModeCall1598A,
		NativeModeCall14237,
		NativeModeCall1548E,
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 11 physical branch = %v, want %v", got, want)
	}
}

func TestPlanNativeUnitMode11StopsAfterBlockedSearchSuccess(t *testing.T) {
	got := PlanNativeUnitMode11(5, 5, true)
	want := []NativeUnitModeAction{
		NativeModeCall1598A,
		NativeModeCall14237,
		NativeModeCall14121,
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 11 blocked-search branch = %v, want %v", got, want)
	}
}
