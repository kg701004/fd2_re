package fdother

import "testing"

func TestTickNativePreparationTimersOnlyEmitsOneToZeroTransitions(t *testing.T) {
	records := make([]byte, 2*0x50)
	records[6], records[5] = 4, 0
	records[0x22], records[0x23], records[0x24] = 1, 2, 0
	// Inactive and selector-mismatched records are untouched.
	records[0x50+6], records[0x50+5], records[0x50+0x22] = 4, 1, 1
	expired, err := TickNativePreparationTimers(records, 2, 4)
	if err != nil {
		t.Fatal(err)
	}
	if len(expired) != 1 || expired[0].RecordIndex != 0 || expired[0].CounterIndex != 0 || expired[0].VisualSourceOffset != 0x1e1 {
		t.Fatalf("expired=%#v", expired)
	}
	if records[0x22] != 0 || records[0x23] != 1 || records[0x50+0x22] != 1 {
		t.Fatalf("records mutated unexpectedly: %d,%d,%d", records[0x22], records[0x23], records[0x50+0x22])
	}
}

func TestTickNativePreparationTimersRejectsTruncatedInput(t *testing.T) {
	if _, err := TickNativePreparationTimers(make([]byte, 0x4f), 1, 0); err == nil {
		t.Fatal("truncated preparation records must fail closed")
	}
}
