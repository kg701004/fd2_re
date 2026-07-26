package battle

import (
	"encoding/binary"
	"fmt"
)

// ScoreNativeAISpellAttack preserves the raw scoring loop at 0x15b77 for
// spell IDs 0..12.  The callback is the caller-owned 0x1f183 gate; it is
// required for IDs 10..12 and intentionally has no gameplay name here.
func ScoreNativeAISpellAttack(records []byte, candidates []byte, spellID, spellValue int, skip func(int) bool) (int, error) {
	if spellID < 0 || spellID > 12 || spellValue < 0 {
		return 0, fmt.Errorf("native AI attack score: invalid spell id/value")
	}
	if spellID >= 10 && skip == nil {
		return 0, fmt.Errorf("native AI attack score: missing 0x1f183 gate")
	}
	if err := validateNativeAISpellCandidates(records, candidates); err != nil {
		return 0, err
	}
	score := 0
	for _, rawIndex := range candidates {
		index := int(rawIndex)
		if spellID >= 10 && skip(index) {
			continue
		}
		record := records[index*nativeRecordSize : (index+1)*nativeRecordSize]
		base := 8
		if int(binary.LittleEndian.Uint16(record[0x40:0x42])) < spellValue {
			base = 24
		}
		// 0x15bbf..0x15bce multiplies the raw +0x08==0 path by the
		// double at 0x50144 (1.5), with x87 toward-zero conversion.
		if record[0x08] == 0 {
			base = base * 3 / 2
		}
		score += base
	}
	return score, nil
}

// ScoreNativeAISpellRecovery preserves the raw spell IDs 13..16 branch:
// score 3 when current HP is below half of max HP, doubled by raw +0x34 bit0.
func ScoreNativeAISpellRecovery(records []byte, candidates []byte, spellID int) (int, error) {
	if spellID < 13 || spellID > 16 {
		return 0, fmt.Errorf("native AI recovery score: unsupported spell id %d", spellID)
	}
	if err := validateNativeAISpellCandidates(records, candidates); err != nil {
		return 0, err
	}
	score := 0
	for _, rawIndex := range candidates {
		record := records[int(rawIndex)*nativeRecordSize : (int(rawIndex)+1)*nativeRecordSize]
		current := int(binary.LittleEndian.Uint16(record[0x40:0x42]))
		max := int(binary.LittleEndian.Uint16(record[0x42:0x44]))
		if current >= max/2 {
			continue
		}
		value := 3
		if record[0x34]&1 != 0 {
			value *= 2
		}
		score += value
	}
	return score, nil
}

func validateNativeAISpellCandidates(records []byte, candidates []byte) error {
	if len(records)%nativeRecordSize != 0 {
		return fmt.Errorf("native AI spell score: malformed record buffer")
	}
	for _, rawIndex := range candidates {
		if int(rawIndex) >= len(records)/nativeRecordSize {
			return fmt.Errorf("native AI spell score: candidate index %d out of range", rawIndex)
		}
	}
	return nil
}
