package fdother

import "testing"

func TestNativeUnitPresentSchedulePreservesAllTwentySevenPresents(t *testing.T) {
	steps := NativeUnitPresentSchedule()
	if err := ValidateNativeUnitPresentSchedule(steps); err != nil {
		t.Fatal(err)
	}
	if len(steps) != 27 {
		t.Fatalf("steps=%d, want 27", len(steps))
	}
	if got := steps[0]; got.Phase != "lmi_intro" || got.Resource != 6 || got.Entry != 0x72 || got.DelayTicks != 1 {
		t.Fatalf("first=%#v", got)
	}
	if got := steps[10]; got.Entry != 0x7c || got.DelayTicks != 1 {
		t.Fatalf("last LMI=%#v", got)
	}
	if got := steps[11]; got.Phase != "lut_contract" || got.Resource != 3 || got.Entry != 5 || got.DelayMs != 10 {
		t.Fatalf("first contract=%#v", got)
	}
	if got := steps[16]; got.Entry != 0 || got.DelayMs != 10 || got.DelayTicks != 2 {
		t.Fatalf("last contract=%#v", got)
	}
	if got := steps[17]; got.Phase != "lut_release" || got.Entry != 0 || got.DelayTicks != 1 {
		t.Fatalf("first release=%#v", got)
	}
	if got := steps[26]; got.Entry != 9 || got.DelayTicks != 1 {
		t.Fatalf("last release=%#v", got)
	}
}

func TestValidateNativeUnitPresentScheduleRejectsShortcuts(t *testing.T) {
	steps := NativeUnitPresentSchedule()
	if err := ValidateNativeUnitPresentSchedule(steps[:6]); err == nil {
		t.Fatal("former six-frame approximation was accepted")
	}
	steps = NativeUnitPresentSchedule()
	steps[16].DelayTicks = 0
	if err := ValidateNativeUnitPresentSchedule(steps); err == nil {
		t.Fatal("middle tail ticks were accepted at the wrong timing")
	}
}
