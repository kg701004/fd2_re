package fdother

import (
	"reflect"
	"testing"
)

func TestPlanNativeUnitMode0PreservesNestedFallbacks(t *testing.T) {
	if got := PlanNativeUnitMode0(true, false, false); !reflect.DeepEqual(
		got,
		[]NativeUnitModeAction{NativeModeCall14EF0},
	) {
		t.Fatalf("successful mode 0 actions = %v", got)
	}
	if got := PlanNativeUnitMode0(false, true, false); !reflect.DeepEqual(
		got,
		[]NativeUnitModeAction{NativeModeCall14EF0, NativeModeCall14121},
	) {
		t.Fatalf("blocked-search mode 0 actions = %v", got)
	}
	want := []NativeUnitModeAction{
		NativeModeCall14EF0,
		NativeModeCall14121,
		NativeModeCall13E9C,
		NativeModeCall13FD4,
	}
	if got := PlanNativeUnitMode0(false, false, false); !reflect.DeepEqual(got, want) {
		t.Fatalf("nested mode 0 fallback actions = %v, want %v", got, want)
	}
	if got := PlanNativeUnitMode0(false, false, true); !reflect.DeepEqual(
		got,
		[]NativeUnitModeAction{NativeModeCall14EF0, NativeModeCall14121, NativeModeCall13E9C},
	) {
		t.Fatalf("nearest-coordinate mode 0 actions = %v", got)
	}
}

func TestPlanNativeUnitMode1UsesSharedRecoveryWithoutNearestFallback(t *testing.T) {
	if got := PlanNativeUnitMode1(true, false); !reflect.DeepEqual(
		got,
		[]NativeUnitModeAction{NativeModeCall14EF0},
	) {
		t.Fatalf("successful mode 1 actions = %v", got)
	}
	if got := PlanNativeUnitMode1(false, true); !reflect.DeepEqual(
		got,
		[]NativeUnitModeAction{NativeModeCall14EF0, NativeModeCall14121},
	) {
		t.Fatalf("blocked-search mode 1 actions = %v", got)
	}
	want := []NativeUnitModeAction{
		NativeModeCall14EF0,
		NativeModeCall14121,
		NativeModeCall13FD4,
	}
	if got := PlanNativeUnitMode1(false, false); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 1 shared recovery actions = %v, want %v", got, want)
	}
}

func TestPlanNativeUnitMode3KeepsLookupIndexAndFallback(t *testing.T) {
	want := []NativeUnitModeAction{
		NativeModeCall14EF0,
		NativeModeCall12C60,
		NativeModeCall14121,
		NativeModeCall13E9C,
		NativeModeCall13FD4,
	}
	if got := PlanNativeUnitMode3(false, -1, false, false, false); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 3 lookup fallback actions = %v, want %v", got, want)
	}
	want = []NativeUnitModeAction{
		NativeModeCall14EF0,
		NativeModeCall12C60,
		NativeModeCall12D7B,
		NativeModeCall14B78,
		NativeModeCall13FD4,
		NativeModeWrite51A83Zero,
	}
	if got := PlanNativeUnitMode3(false, 4, false, false, false); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 3 found-index actions = %v, want %v", got, want)
	}
}

func TestPlanNativeUnitMode4And10ReuseMovementRecovery(t *testing.T) {
	want := []NativeUnitModeAction{
		NativeModeWrite51A83Zero,
		NativeModeCall12D7B,
		NativeModeCall14B78,
		NativeModeCall13FD4,
	}
	if got := PlanNativeUnitMode4(false); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 4 actions = %v, want %v", got, want)
	}
	want = append([]NativeUnitModeAction{NativeModeCall14EF0}, want...)
	if got := PlanNativeUnitMode10(false, false); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 10 actions = %v, want %v", got, want)
	}
}

func TestPlanNativeUnitMode5PreservesArrivalWrites(t *testing.T) {
	input := NativeUnitMode5Inputs{
		EventLookupSucceeded:     true,
		ArrivedAtEventCoordinate: true,
		EventRecordType:          0,
	}
	want := []NativeUnitModeAction{
		NativeModeCall14EF0,
		NativeModeWrite51A83Zero,
		NativeModeCall12D7B,
		NativeModeCall15DF3,
		NativeModeCall14B78,
		NativeModeCall13FD4,
		NativeModeWriteUnit31And32,
		NativeModeCall1BB8C,
		NativeModeWrite53AD5One,
		NativeModeCall25B45,
		NativeModeCall12263,
		NativeModeWriteUnit34Mode7,
	}
	if got := PlanNativeUnitMode5(input); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 5 arrival actions = %v, want %v", got, want)
	}
	input.EventRecordType = 2
	got := PlanNativeUnitMode5(input)
	for _, action := range got {
		if action == NativeModeWriteUnit31And32 || action == NativeModeCall1BB8C {
			t.Fatalf("mode 5 type>=2 unexpectedly writes/calls: %v", got)
		}
	}
}

func TestPlanNativeUnitMode5StateAndLookupFallback(t *testing.T) {
	for _, input := range []NativeUnitMode5Inputs{
		{EventStateByte: 1},
		{EventLookupSucceeded: false},
	} {
		want := []NativeUnitModeAction{
			NativeModeCall14EF0,
			NativeModeWrite51A83Zero,
			NativeModeCall12D7B,
			NativeModeCall14121,
			NativeModeCall13E9C,
			NativeModeCall13FD4,
		}
		if got := PlanNativeUnitMode5(input); !reflect.DeepEqual(got, want) {
			t.Fatalf("mode 5 fallback actions = %v, want %v", got, want)
		}
	}
}

func TestPlanNativeUnitMode7And9PreserveCoordinateGates(t *testing.T) {
	want := []NativeUnitModeAction{
		NativeModeWrite51A83Zero,
		NativeModeCall12D7B,
		NativeModeCall14B78,
		NativeModeCall13FD4,
		NativeModeCall32975,
	}
	if got := PlanNativeUnitMode7(false, true); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 7 actions = %v, want %v", got, want)
	}
	want = []NativeUnitModeAction{
		NativeModeCall12C60,
		NativeModeCall14EF0,
		NativeModeCall14121,
		NativeModeCall13E9C,
		NativeModeCall13FD4,
	}
	if got := PlanNativeUnitMode9(-1, false, false, false, false); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 9 general fallback actions = %v, want %v", got, want)
	}
	want = []NativeUnitModeAction{
		NativeModeCall12C60,
		NativeModeCall12D7B,
		NativeModeCall14B78,
		NativeModeCall13FD4,
	}
	if got := PlanNativeUnitMode9(6, true, true, true, false); !reflect.DeepEqual(got, want) {
		t.Fatalf("mode 9 found-index actions = %v, want %v", got, want)
	}
}

func TestPlanNativeUnitMode2PreservesSharedRecovery(t *testing.T) {
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
