package fdother

import "testing"

func TestFindNativePhaseDispatchCandidatesUsesRawGates(t *testing.T) {
	raw := make([]byte, 3*0x50)
	raw[6] = 1
	raw[0x50+6] = 1
	raw[0x50+5] = 0x80
	raw[2*0x50+6] = 1
	raw[2*0x50+0x26] = 1
	got, err := FindNativePhaseDispatchCandidates(raw, 3)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].UnitIndex != 0 || got[0].SelectorArg != 1 {
		t.Fatalf("candidates = %#v", got)
	}
}

func TestFindNativePhaseDispatchCandidatesRejectsTruncatedInput(t *testing.T) {
	if _, err := FindNativePhaseDispatchCandidates(make([]byte, 0x50-1), 1); err == nil {
		t.Fatal("expected truncated raw records to fail closed")
	}
}

func TestFindNativePhaseDispatchCandidatesAllowsZeroCountWithoutStorage(t *testing.T) {
	got, err := FindNativePhaseDispatchCandidates(nil, 0)
	if err != nil || len(got) != 0 {
		t.Fatalf("zero-count result = %#v, %v", got, err)
	}
}
