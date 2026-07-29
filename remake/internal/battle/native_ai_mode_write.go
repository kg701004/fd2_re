package battle

import "fmt"

// SetNativeAIModeRange reproduces 0x3419c. It updates the low nibble of
// runtime record +0x34 for every inclusive unit index while preserving the
// high-nibble flags.
func SetNativeAIModeRange(
	records []byte,
	count, first, last int,
	mode byte,
) error {
	if count < 0 || count > len(records)/nativeRecordSize ||
		first < 0 || last < first || last >= count || mode > 0x0f {
		return fmt.Errorf("native AI mode range is out of bounds")
	}
	for unit := first; unit <= last; unit++ {
		offset := unit*nativeRecordSize + 0x34
		records[offset] = records[offset]&0xf0 | mode
	}
	return nil
}

// SetNativeAIModeByte preserves the full-byte writer used by the mode-5
// completion branch at 0x13d20 and several chapter handlers. Unlike
// SetNativeAIModeRange, it intentionally replaces high-nibble flags.
func SetNativeAIModeByte(records []byte, count, unit int, value byte) error {
	if count < 0 || count > len(records)/nativeRecordSize || unit < 0 || unit >= count {
		return fmt.Errorf("native AI mode unit is out of bounds")
	}
	records[unit*nativeRecordSize+0x34] = value
	return nil
}
