package battle

import (
	"encoding/binary"
	"testing"
)

func TestScoreNativeAISpellAttackPreservesRawBranches(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:], 10)
	binary.LittleEndian.PutUint16(records[nativeRecordSize+0x40:], 20)
	got, err := ScoreNativeAISpellAttack(records, []byte{0, 1}, 0, 15, nil)
	if err != nil || got != 48 { // 24*1.5 + 8*1.5, toward-zero
		t.Fatalf("score=%d err=%v", got, err)
	}
	if _, err := ScoreNativeAISpellAttack(records, []byte{0}, 10, 15, nil); err == nil {
		t.Fatal("ID10 accepted without its raw inactive gate")
	}
	got, err = ScoreNativeAISpellAttack(records, []byte{0, 1}, 10, 15, func(index int) bool { return index == 1 })
	if err != nil || got != 36 {
		t.Fatalf("gated score=%d err=%v", got, err)
	}
}

func TestScoreNativeAISpellRecoveryUsesHalfAndRawBit(t *testing.T) {
	records := make([]byte, nativeRecordSize)
	binary.LittleEndian.PutUint16(records[0x40:], 4)
	binary.LittleEndian.PutUint16(records[0x42:], 10)
	records[0x34] = 1
	got, err := ScoreNativeAISpellRecovery(records, []byte{0}, 13)
	if err != nil || got != 6 {
		t.Fatalf("score=%d err=%v", got, err)
	}
	binary.LittleEndian.PutUint16(records[0x40:], 5)
	got, err = ScoreNativeAISpellRecovery(records, []byte{0}, 13)
	if err != nil || got != 0 {
		t.Fatalf("half-health score=%d err=%v", got, err)
	}
}

func TestScoreNativeAISpellRejectsMalformedCandidates(t *testing.T) {
	if _, err := ScoreNativeAISpellRecovery(make([]byte, nativeRecordSize-1), []byte{0}, 13); err == nil {
		t.Fatal("malformed record buffer accepted")
	}
	if _, err := ScoreNativeAISpellAttack(make([]byte, nativeRecordSize), []byte{1}, 0, 1, nil); err == nil {
		t.Fatal("out-of-range candidate accepted")
	}
}
