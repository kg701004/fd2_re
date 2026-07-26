package battle

import (
	"encoding/binary"
	"testing"
)

func TestApplyNativePersistentRecordCopyPreservesProvenMutationCore(t *testing.T) {
	runtime := make([]byte, nativeRecordSize)
	persistent := make([]byte, nativeRecordSize)
	runtime[5] = 0xff
	runtime[0x22], runtime[0x27] = 7, 9
	binary.LittleEndian.PutUint16(runtime[0x40:0x42], 11)
	binary.LittleEndian.PutUint16(runtime[0x42:0x44], 22)
	binary.LittleEndian.PutUint16(runtime[0x44:0x46], 33)
	binary.LittleEndian.PutUint16(runtime[0x46:0x48], 44)
	if err := ApplyNativePersistentRecordCopy(runtime, persistent, 0, 0); err != nil {
		t.Fatal(err)
	}
	if persistent[0x22] != 0 || persistent[0x27] != 0 || persistent[5] != 1 {
		t.Fatalf("status bytes=%#x/%#x/%#x", persistent[5], persistent[0x22], persistent[0x27])
	}
	if got := binary.LittleEndian.Uint16(persistent[0x40:0x42]); got != 11 {
		t.Fatalf("+40=%d, want copied runtime value 11 when byte5==1", got)
	}
	if got := binary.LittleEndian.Uint16(persistent[0x44:0x46]); got != 44 {
		t.Fatalf("+44=%d, want 44", got)
	}
}

func TestApplyNativePersistentRecordCopyNonOneByte5CopiesWord40(t *testing.T) {
	runtime := make([]byte, nativeRecordSize)
	persistent := make([]byte, nativeRecordSize)
	runtime[5] = 0x80
	binary.LittleEndian.PutUint16(runtime[0x42:0x44], 0x1234)
	binary.LittleEndian.PutUint16(runtime[0x46:0x48], 0x5678)
	if err := ApplyNativePersistentRecordCopy(runtime, persistent, 0, 0); err != nil {
		t.Fatal(err)
	}
	if got := binary.LittleEndian.Uint16(persistent[0x40:0x42]); got != 0x1234 {
		t.Fatalf("+40=%#x, want 0x1234", got)
	}
}

func TestApplyNativePersistentRecordCopyPreflightsBothBuffers(t *testing.T) {
	if err := ApplyNativePersistentRecordCopy(make([]byte, nativeRecordSize-1), make([]byte, nativeRecordSize), 0, 0); err == nil {
		t.Fatal("short runtime record unexpectedly accepted")
	}
	if err := ApplyNativePersistentRecordCopy(make([]byte, nativeRecordSize), make([]byte, nativeRecordSize-1), 0, 0); err == nil {
		t.Fatal("short persistent record unexpectedly accepted")
	}
}
