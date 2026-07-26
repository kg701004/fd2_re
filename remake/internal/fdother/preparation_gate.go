package fdother

import (
	"encoding/binary"
	"errors"
)

// NativePreparationRecord is the raw subset consumed by 0x1a866.  Field
// names intentionally preserve offsets: their higher-level gameplay meaning
// is not established by this caller.
type NativePreparationRecord struct {
	Raw25  byte
	Raw5   byte
	Raw6   byte
	Raw7   byte
	Word40 uint16
	Word42 uint16
}

// ParseNativePreparationRecord extracts only the bytes read by 0x1a866 from
// one 0x50-byte unit record.  Short records fail closed.
func ParseNativePreparationRecord(raw []byte) (NativePreparationRecord, error) {
	if len(raw) < 0x44 {
		return NativePreparationRecord{}, errors.New("fdother: preparation record is shorter than 0x44 bytes")
	}
	return NativePreparationRecord{
		Raw25: raw[0x25], Raw5: raw[5], Raw6: raw[6], Raw7: raw[7],
		Word40: binary.LittleEndian.Uint16(raw[0x40:]),
		Word42: binary.LittleEndian.Uint16(raw[0x42:]),
	}, nil
}

// NativePreparationEligible reproduces the exact three raw gates in 0x1a866
// for the caller-supplied selector.  It deliberately does not call the
// presentation functions that follow the gate.
func NativePreparationEligible(record NativePreparationRecord, selector int) bool {
	return record.Raw25 != 0 && int(record.Raw6) == selector && record.Raw5&1 == 0
}

// NativePreparationAdjustedWord40 returns the post-gate word+0x40 value and
// the raw divisor written to global state.  Native code uses signed division
// on the zero-extended word+0x42 and clamps the subtraction at zero.
func NativePreparationAdjustedWord40(record NativePreparationRecord) (adjusted uint16, divisor int) {
	divisor = int(record.Word42) / 10
	if int(record.Word40)-divisor < 0 {
		return 0, divisor
	}
	return record.Word40 - uint16(divisor), divisor
}
