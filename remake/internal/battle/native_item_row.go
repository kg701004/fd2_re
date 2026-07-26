package battle

import "fmt"

const (
	// NativeItemEffectTableBase is the linear address used by 0x4e56c after
	// relocation into the EXE data image.  The helper below returns an offset
	// relative to that table; it does not assign names to the row fields.
	NativeItemEffectTableBase = 0x602ad
	NativeItemEffectRowSize   = 0x17
)

// NativeItemEffectRowOffset reproduces 0x4e56c(item): item rows are selected
// with a 23-byte stride from the table base.  The native routine has no bounds
// check, so this adapter validates the byte-sized selector and returns only
// the proven table-relative offset.
func NativeItemEffectRowOffset(item int) (int, error) {
	if item < 0 || item > 0xff {
		return 0, fmt.Errorf("native item selector %d is out of bounds", item)
	}
	return item * NativeItemEffectRowSize, nil
}
