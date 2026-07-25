package battle

import "fmt"

// SetInitialCommandMask materializes the exact constructor input for native
// unit+0x1a..+0x1e.  An absent JSON field is accepted for legacy editable
// scenarios and yields a zero mask; any non-empty malformed field is rejected
// rather than being truncated into a different command inventory.
func (u *Unit) SetInitialCommandMask(raw []byte) error {
	if u == nil {
		return fmt.Errorf("nil unit")
	}
	if len(raw) != 0 && len(raw) != 4 {
		return fmt.Errorf("want 4 bytes, got %d", len(raw))
	}
	var next [5]byte
	copy(next[:4], raw)
	u.NativeCommandMask = next
	return nil
}

// NativeCommandIDs expands the five-byte bitset in exactly the original
// byte-major, low-bit-first order used by 0x1c269.
func (u *Unit) NativeCommandIDs() []int {
	if u == nil {
		return nil
	}
	ids := make([]int, 0, 40)
	for byteIndex, value := range u.NativeCommandMask {
		for bit := 0; bit < 8; bit++ {
			if value&(1<<bit) != 0 {
				ids = append(ids, byteIndex*8+bit)
			}
		}
	}
	return ids
}

// EnableNativeCommand mirrors the bounded OR write performed by 0x1d7fb.
// It only changes the native inventory bit; it does not claim the command is
// executable until its record/effect path has separately been recovered.
func (u *Unit) EnableNativeCommand(id int) bool {
	if u == nil || id < 0 || id >= 40 {
		return false
	}
	u.NativeCommandMask[id/8] |= 1 << (id % 8)
	return true
}
