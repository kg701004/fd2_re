package battle

import (
	"encoding/binary"
	"testing"
)

func TestScoreNativeAIItemCommandTargetsType5And13(t *testing.T) {
	records := make([]byte, 3*nativeRecordSize)
	setHP := func(index, current, maximum int, raw34 byte) {
		record := records[index*nativeRecordSize:]
		binary.LittleEndian.PutUint16(record[0x40:0x42], uint16(current))
		binary.LittleEndian.PutUint16(record[0x42:0x44], uint16(maximum))
		record[0x34] = raw34
	}
	setHP(0, 30, 90, 0)
	setHP(1, 45, 90, 0)
	setHP(2, 46, 90, 0x80)
	for _, itemType := range []int{5, 0x0d} {
		got, err := ScoreNativeAIItemCommandTargets(
			records, []byte{0, 1, 2}, itemType, 0, nil,
		)
		if err != nil || got != 11 {
			t.Fatalf("type=%#x score=%d err=%v want 11", itemType, got, err)
		}
	}
}

func TestScoreNativeAIItemCommandTargetsThresholdFamilies(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:0x42], 20)
	binary.LittleEndian.PutUint16(records[nativeRecordSize+0x40:], 21)
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	book[2].Damage = 20
	for _, itemType := range []int{0x14, 0x15} {
		got, err := ScoreNativeAIItemCommandTargets(
			records, []byte{0, 1}, itemType, 2, book,
		)
		if err != nil || got != 0x1a {
			t.Fatalf("type=%#x score=%d err=%v want 26", itemType, got, err)
		}
	}
	got, err := ScoreNativeAIItemCommandTargets(
		records, []byte{0, 1}, 0x18, 20, nil,
	)
	if err != nil || got != 0x1a {
		t.Fatalf("type=0x18 score=%d err=%v want 26", got, err)
	}
}

func TestScoreNativeAIItemCommandTargetsFailsClosed(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	if _, err := ScoreNativeAIItemCommandTargets(
		records, []byte{1}, 5, 0, nil,
	); err == nil {
		t.Fatal("out-of-range target accepted")
	}
	if _, err := ScoreNativeAIItemCommandTargets(
		records, []byte{0}, 0x14, 2, nil,
	); err == nil {
		t.Fatal("missing 0x4e516 command record accepted")
	}
}
