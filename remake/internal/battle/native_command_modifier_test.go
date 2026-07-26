package battle

import "testing"

func TestApplyNativeCommandModifierDispatchesVerifiedBranches(t *testing.T) {
	for _, commandID := range []int{17, 18, 19} {
		records := make([]byte, nativeRecordSize)
		result, err := ApplyNativeCommandModifier(records, []byte{0}, commandID, 0)
		if err != nil {
			t.Fatalf("command %d: %v", commandID, err)
		}
		if result.CommandID != commandID || result.RNGState == 0 && commandID == 17 {
			// RNG state is allowed to remain zero only when a branch is marked;
			// this assertion mainly verifies the command-specific union below.
			t.Fatalf("command %d result=%+v", commandID, result)
		}
		if commandID < 19 && len(result.WordSteps) != 1 {
			t.Fatalf("command %d word steps=%v", commandID, result.WordSteps)
		}
		if commandID == 19 && len(result.PairSteps) != 1 {
			t.Fatalf("command 19 pair steps=%v", result.PairSteps)
		}
	}
}

func TestApplyNativeCommandModifierFailsClosedOnUnsupportedID(t *testing.T) {
	if _, err := ApplyNativeCommandModifier(make([]byte, nativeRecordSize), []byte{0}, 16, 0); err == nil {
		t.Fatal("unsupported command modifier accepted")
	}
}
