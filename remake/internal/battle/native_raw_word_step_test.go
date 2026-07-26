package battle

import "testing"

func TestApplyNativeRawWordStepMatchesMarkerDeltaAndScore(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[0x20], records[0x21] = 9, 2
	records[0x48], records[0x49] = 100, 0
	records[nativeRecordSize+0x22] = 1
	records[nativeRecordSize+0x48], records[nativeRecordSize+0x49] = 200, 0
	got, finalState, score, err := ApplyNativeRawWordStep(records, []byte{0, 1}, 0)
	if err != nil {
		t.Fatal(err)
	}
	if finalState != 0x80a4 || len(got) != 2 || !got[0].Processed || got[0].Marker != 2 || got[0].Delta != 16 || got[1].Processed || score != 64 {
		t.Fatalf("results=%#v state=%#x score=%d", got, finalState, score)
	}
	if records[0x48] != 116 || records[nativeRecordSize+0x48] != 200 {
		t.Fatalf("words=%d,%d", records[0x48], records[nativeRecordSize+0x48])
	}
}

func TestApplyNativeRawWordStepRejectsBadIndexBeforeMutation(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x22], records[0x48] = 0, 100
	if _, _, _, err := ApplyNativeRawWordStep(records, []byte{0, 1}, 0); err == nil {
		t.Fatal("expected bad index to fail closed")
	}
	if records[0x22] != 0 || records[0x48] != 100 {
		t.Fatal("bad input mutated records")
	}
}

func TestApplyNativeRawWordStepAtOffsetsMatches22866Family(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x20], records[0x21] = 10, 1
	records[0x4a], records[0x4b] = 100, 0
	got, state, score, err := ApplyNativeRawWordStepAtOffsets(records, []byte{0}, 0, 0x23, 0x4a)
	if err != nil || state != 0x80a4 || len(got) != 1 || !got[0].Processed || got[0].Marker != 2 || got[0].Delta != 16 || score != 62 {
		t.Fatalf("results=%#v state=%#x score=%d err=%v", got, state, score, err)
	}
	if records[0x23] != 2 || records[0x4a] != 116 {
		t.Fatalf("raw offsets = %#x %#x", records[0x23], records[0x4a])
	}
}
