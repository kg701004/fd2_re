package fdother

import "testing"

func TestFindNativePreparationDispatchUsesOverlappingThreeByteStride(t *testing.T) {
	table := make([]byte, 51)
	// Slot 2 starts at 6; its +3/+5 gates and +4 callback index overlap the
	// neighboring raw bytes exactly as the native address arithmetic does.
	table[6+3], table[6+4], table[6+5] = 0x2a, 0x17, 0x09
	// A second matching slot proves the scan does not stop after first hit.
	table[9+3], table[9+4], table[9+5] = 0x2a, 0x22, 0x09
	matches, err := FindNativePreparationDispatch(table, 0x2a, 0x09)
	if err != nil {
		t.Fatal(err)
	}
	if len(matches) != 2 || matches[0].Slot != 2 || matches[0].FunctionIndex != 0x17 || matches[1].Slot != 3 || matches[1].FunctionIndex != 0x22 {
		t.Fatalf("matches=%#v", matches)
	}
}

func TestFindNativePreparationDispatchRejectsShortTable(t *testing.T) {
	if _, err := FindNativePreparationDispatch(make([]byte, 50), 0, 0); err == nil {
		t.Fatal("short overlapping dispatch table must fail closed")
	}
}
