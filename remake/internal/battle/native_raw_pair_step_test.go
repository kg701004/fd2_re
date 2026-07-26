package battle

import "testing"

func TestApplyNativeRawPairStepMatches22997Offsets(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x20], records[0x21] = 9, 2
	records[0x4c], records[0x4d] = 0xfe, 0xff
	records[0x4e], records[0x4f] = 1, 0
	got, state, score, err := ApplyNativeRawPairStep(records, []byte{0}, 0)
	if err != nil || state != 0x80a4 || len(got) != 1 || !got[0].Processed || got[0].Marker != 2 || score != 64 {
		t.Fatalf("results=%#v state=%#x score=%d err=%v", got, state, score, err)
	}
	if records[0x24] != 2 || records[0x4c] != 13 || records[0x4d] != 0 || records[0x4e] != 16 || records[0x4f] != 0 {
		t.Fatalf("raw pair = %#x %#x %#x %#x", records[0x4c], records[0x4d], records[0x4e], records[0x4f])
	}
}

func TestApplyNativeRawPairStepSkipsMarkedAndPreflights(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x24] = 1
	got, state, score, err := ApplyNativeRawPairStep(records, []byte{0}, 0)
	if err != nil || state != 0 || score != 0 || got[0].Processed {
		t.Fatalf("marked result=%#v state=%#x score=%d err=%v", got, state, score, err)
	}
	if _, _, _, err := ApplyNativeRawPairStep(records, []byte{1}, 0); err == nil {
		t.Fatal("expected bad index to fail closed")
	}
}
