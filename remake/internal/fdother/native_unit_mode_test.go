package fdother

import "testing"

func TestPlanNativeUnitModeMasksModeAndPreservesRawArguments(t *testing.T) {
	raw := make([]byte, 0x3e)
	raw[0x34] = 0xf9
	raw[0x35] = 0x80
	raw[0x36] = 0x17
	raw[0x3d] = 0x04
	got, err := PlanNativeUnitMode(raw, 7, 1)
	if err != nil || got == nil {
		t.Fatalf("plan = %#v, err=%v", got, err)
	}
	if got.UnitIndex != 7 || got.CallerArg != 1 || got.Mode != 9 || got.RawArg35 != 0x80 || got.RawArg36 != 0x17 || got.RawCounter != 4 {
		t.Fatalf("plan = %#v", got)
	}
}

func TestPlanNativeUnitModeRejectsGatedRecordWithoutMutation(t *testing.T) {
	raw := make([]byte, 0x3e)
	raw[5] = 0x04
	raw[0x34] = 3
	got, err := PlanNativeUnitMode(raw, 0, 1)
	if err != nil || got != nil {
		t.Fatalf("gated plan = %#v, err=%v", got, err)
	}
}

func TestPlanNativeUnitModeRejectsShortRecord(t *testing.T) {
	if _, err := PlanNativeUnitMode(make([]byte, 0x3d), 0, 0); err == nil {
		t.Fatal("expected short record to fail closed")
	}
}
