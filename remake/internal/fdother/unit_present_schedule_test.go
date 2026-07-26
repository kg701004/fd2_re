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

func TestNativeUnitPresentByteOriginMatches22470AddressExpression(t *testing.T) {
	got := NativeUnitPresentByteOrigin(22, 23, 16, 19)
	want := 0x8088 + 0x18*(22-16) + 0x18*0x1c8*(23-19) + 0x1c8
	if got != want {
		t.Fatalf("origin=%#x, want %#x", got, want)
	}
	// Keep raw signed arithmetic: clipping is a renderer/caller decision, and
	// must not be silently folded into the recovered native address formula.
	if got := NativeUnitPresentByteOrigin(0, 0, 1, 1); got != 0x8088-0x18-0x18*0x1c8+0x1c8 {
		t.Fatalf("offscreen origin=%#x", got)
	}
}
