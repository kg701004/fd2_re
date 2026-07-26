package battle

import "fmt"

// NativeInventoryAvailableCount is the Unit-facing form of 0x1b8a6. It
// counts the eight raw flags whose sign bit is clear, independently of item
// bytes. Callers must supply the constructor's complete eight-byte flag view;
// a compact inventory length is not an equivalent substitute.
func NativeInventoryAvailableCount(flags []int) (int, error) {
	if len(flags) != nativeInventoryCells {
		return 0, fmt.Errorf("native inventory available: flags length=%d, want %d", len(flags), nativeInventoryCells)
	}
	count := 0
	for slot, flag := range flags {
		if flag < 0 || flag > 0xff {
			return 0, fmt.Errorf("native inventory available: malformed flag %d", slot)
		}
		if flag&0x80 == 0 {
			count++
		}
	}
	return count, nil
}
