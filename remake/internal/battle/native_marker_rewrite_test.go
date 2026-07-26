package battle

import "testing"

func TestRewriteNativeMarker1FMutatesOnlyMatchingTailSlots(t *testing.T) {
	records := make([]byte, 19*nativeRecordSize)
	records[16*nativeRecordSize+7] = 0x1f
	records[17*nativeRecordSize+7] = 0x20
	records[18*nativeRecordSize+7] = 0x1f
	if err := RewriteNativeMarker1F(records, 19); err != nil {
		t.Fatal(err)
	}
	if records[16*nativeRecordSize] != 0x10 || records[16*nativeRecordSize+1] != 0x06 {
		t.Fatalf("slot16 prefix=%x/%x", records[16*nativeRecordSize], records[16*nativeRecordSize+1])
	}
	if records[17*nativeRecordSize] != 0 || records[17*nativeRecordSize+1] != 0 {
		t.Fatal("nonmatching marker mutated")
	}
	if records[18*nativeRecordSize] != 0x10 || records[18*nativeRecordSize+1] != 0x06 {
		t.Fatal("slot18 marker not rewritten")
	}
}

func TestRewriteNativeMarker1FLeavesPrefixAndRejectsCount(t *testing.T) {
	records := make([]byte, 0x10*nativeRecordSize)
	if err := RewriteNativeMarker1F(records, 0x10); err != nil {
		t.Fatal(err)
	}
	if err := RewriteNativeMarker1F(records, 0x11); err == nil {
		t.Fatal("short record buffer unexpectedly accepted")
	}
	if err := RewriteNativeMarker1F(records, -1); err == nil {
		t.Fatal("negative count unexpectedly accepted")
	}
}
