package fdother

import "testing"

func TestApplyNativePreparationInputMatchesScancodeBranches(t *testing.T) {
	confirm := []byte{0xe0, 0x52, 0x1c, 0x39}
	for _, scan := range confirm {
		state := 1
		if got := ApplyNativePreparationInput(scan, &state); got != NativePreparationInputConfirm || state != 0 {
			t.Fatalf("confirm %#x => result=%d state=%d", scan, got, state)
		}
	}
	cancel := []byte{0x01, 0x53}
	for _, scan := range cancel {
		state := 1
		if got := ApplyNativePreparationInput(scan, &state); got != NativePreparationInputCancel || state != 0 {
			t.Fatalf("cancel %#x => result=%d state=%d", scan, got, state)
		}
	}
	for _, tc := range []struct {
		scan  byte
		state int
		want  int
	}{
		{0x4b, 1, 0}, {0x4d, 0, 1}, {0x7f, 1, 1},
	} {
		state := tc.state
		if got := ApplyNativePreparationInput(tc.scan, &state); got != NativePreparationInputContinue || state != tc.want {
			t.Fatalf("continue %#x => result=%d state=%d", tc.scan, got, state)
		}
	}
}
