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
// score 8 below max/3, score 3 below max/2, otherwise zero; raw +0x34 bit0
// doubles the selected score.
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
		value := 0
		if max/3 > current {
			value = 8
		} else if max/2 > current {
			value = 3
		}
		if record[0x34]&1 != 0 {
			value *= 2
		}
		score += value
	}
	return score, nil
}

// ScoreNativeAISpellFlag preserves the ID20/21 branches: each nonzero raw
// +0x25/+0x26 flag contributes six points. The byte remains unnamed and this
// function does not apply or clear it.
func ScoreNativeAISpellFlag(records []byte, candidates []byte, spellID int) (int, error) {
	offset := 0
	switch spellID {
	case 20:
		offset = 0x25
	case 21:
		offset = 0x26
	default:
		return 0, fmt.Errorf("native AI flag score: unsupported spell id %d", spellID)
	}
	if err := validateNativeAISpellCandidates(records, candidates); err != nil {
		return 0, err
	}
	score := 0
	for _, rawIndex := range candidates {
		record := records[int(rawIndex)*nativeRecordSize : (int(rawIndex)+1)*nativeRecordSize]
		if record[offset] != 0 {
			score += 6
		}
	}
	return score, nil
}

// ScoreNativeAISpellZeroFlag preserves the 0x15b77 helper branches that add
// a score when a raw byte is zero: IDs17/18/19 use +0x22/+0x23/+0x24 and add
// three; IDs26/27 use +0x25/+0x26 and add four.
func ScoreNativeAISpellZeroFlag(records []byte, candidates []byte, spellID int) (int, error) {
	offset, increment := 0, 0
	switch spellID {
	case 17:
		offset, increment = 0x22, 3
	case 18:
		offset, increment = 0x23, 3
	case 19:
		offset, increment = 0x24, 3
	case 26:
		offset, increment = 0x25, 4
	case 27:
		offset, increment = 0x26, 4
	default:
		return 0, fmt.Errorf("native AI zero-flag score: unsupported spell id %d", spellID)
	}
	if err := validateNativeAISpellCandidates(records, candidates); err != nil {
		return 0, err
	}
	score := 0
	for _, rawIndex := range candidates {
		record := records[int(rawIndex)*nativeRecordSize : (int(rawIndex)+1)*nativeRecordSize]
		if record[offset] == 0 {
			score += increment
		}
	}
	return score, nil
}

// ScoreNativeAISpell22 preserves the ID22 branch at 0x15d30: a zero raw
// +0x27 gate followed by 0x1c269(unit, nil), which scans raw +0x1a..+0x1e
// bits. A candidate with any set bit contributes six points. The bytes are
// intentionally left unnamed and untouched.
func ScoreNativeAISpell22(records []byte, candidates []byte) (int, error) {
	if err := validateNativeAISpellCandidates(records, candidates); err != nil {
		return 0, err
	}
	score := 0
	for _, rawIndex := range candidates {
		record := records[int(rawIndex)*nativeRecordSize : (int(rawIndex)+1)*nativeRecordSize]
		if record[0x27] != 0 {
			continue
		}
		set := false
		for _, b := range record[0x1a:0x1f] {
			if b != 0 {
				set = true
				break
			}
		}
		if set {
			score += 6
		}
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
