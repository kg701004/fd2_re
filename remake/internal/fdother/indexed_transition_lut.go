package fdother

import "fmt"

// NativeIndexedTransitionLUT resolves the raw descriptor index used by
// 0x24618/0x22046 into one FDOTHER#3 256-byte remap table. The native loop
// visits indices 9..1; index 0 and every other bank entry belong to different
// callers and are rejected here rather than silently reused.
func NativeIndexedTransitionLUT(bank [][]byte, descriptor int) ([]byte, error) {
	if descriptor < 1 || descriptor > 9 || descriptor >= len(bank) {
		return nil, fmt.Errorf("indexed transition: descriptor %d outside native 1..9 bank", descriptor)
	}
	if len(bank[descriptor]) != 256 {
		return nil, fmt.Errorf("indexed transition: descriptor %d has %d bytes, want 256", descriptor, len(bank[descriptor]))
	}
	return append([]byte(nil), bank[descriptor]...), nil
}
