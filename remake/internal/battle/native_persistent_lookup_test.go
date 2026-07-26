package battle

import "testing"

func TestFindNativePersistentIdentityUsesCountStrideAndByteOffset(t *testing.T) {
	records := make([]byte, 4*nativePersistentRecordSize)
	records[1*nativePersistentRecordSize+0x08] = 12
	records[3*nativePersistentRecordSize+0x08] = 12
	before := append([]byte(nil), records...)
	index, ok, err := FindNativePersistentIdentity(records, 3, 12)
	if err != nil || !ok || index != 1 {
		t.Fatalf("got (%d,%v,%v), want (1,true,nil)", index, ok, err)
	}
	if string(records) != string(before) {
		t.Fatal("persistent lookup mutated records")
	}
	if _, ok, err := FindNativePersistentIdentity(records, 3, 13); err != nil || ok {
		t.Fatalf("missing got ok=%v err=%v, want false,nil", ok, err)
	}
}

func TestFindNativePersistentIdentityRejectsCountAndShortBuffer(t *testing.T) {
	if _, _, err := FindNativePersistentIdentity(make([]byte, 32*nativePersistentRecordSize), 33, 1); err == nil {
		t.Fatal("count above native persistent capacity unexpectedly accepted")
	}
	if _, _, err := FindNativePersistentIdentity(make([]byte, nativePersistentRecordSize-1), 1, 1); err == nil {
		t.Fatal("short persistent record unexpectedly accepted")
	}
}
