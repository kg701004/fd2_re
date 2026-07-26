package battle

import "testing"

func TestClearNativeUnitByteMatchesRawMutationAndEffectiveValue(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[0x14] = 1
	records[0x20] = 9
	records[0x21] = 2
	records[nativeRecordSize+0x14] = 0
	got, total, err := ClearNativeUnitByte(records, []byte{0, 1}, 0x14)
	if err != nil {
		t.Fatal(err)
	}
	if records[0x14] != 0 || len(got) != 2 || !got[0].Cleared || got[0].RawValue != 4*32 || got[1].Cleared || total != 4*32 {
		t.Fatalf("results=%#v total=%d records=%#x", got, total, records[0x14])
	}
}

func TestClearNativeUnitByteDoesNotAddThirtyAtBoundary(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	records[0x16] = 1
	records[0x20] = 25
	records[0x21] = 3
	got, total, err := ClearNativeUnitByte(records, []byte{0}, 0x16)
	if err != nil || !got[0].Cleared || total != 12 {
		t.Fatalf("results=%#v total=%d err=%v", got, total, err)
	}
}

func TestClearNativeUnitByteRejectsBadFieldOrIndex(t *testing.T) {
	if _, _, err := ClearNativeUnitByte(make([]byte, nativeRecordSize), []byte{0}, nativeRecordSize); err == nil {
		t.Fatal("expected bad field offset to fail closed")
	}
	if _, _, err := ClearNativeUnitByte(make([]byte, nativeRecordSize), []byte{1}, 0x14); err == nil {
		t.Fatal("expected bad unit index to fail closed")
	}
}
