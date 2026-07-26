package battle

import "fmt"

const (
	// NativeClassCompatibilityTableBase is the relocated EXE table used by
	// 0x4e53e.  The six-byte compatibility predicate consumes the first six
	// bytes of each seven-byte row; the seventh byte remains opaque.
	NativeClassCompatibilityTableBase = 0x6188a
	NativeClassCompatibilityRowSize   = 7
)

// NativeClassCompatibilityRowOffset preserves the proven address arithmetic
// of 0x4e53e(class): table base + class*7.  It intentionally returns only a
// table-relative offset; row bytes are not assigned gameplay names.
func NativeClassCompatibilityRowOffset(classID int) (int, error) {
	if classID < 0 || classID > 0xff {
		return 0, fmt.Errorf("native class selector %d is out of bounds", classID)
	}
	return classID * NativeClassCompatibilityRowSize, nil
}

// NativeClassItemCompatible reproduces 0x1c1c3's six-byte comparison.  The
// caller must provide the exact row returned by 0x4e53e; short rows fail
// closed rather than treating missing bytes as compatible.
func NativeClassItemCompatible(itemRowByte0 byte, classRow []byte) (bool, error) {
	if len(classRow) < 6 {
		return false, fmt.Errorf("native class compatibility row too short: %d", len(classRow))
	}
	for _, candidate := range classRow[:6] {
		if candidate == itemRowByte0 {
			return true, nil
		}
	}
	return false, nil
}
