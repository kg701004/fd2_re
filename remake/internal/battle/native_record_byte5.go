package battle

import "fmt"

// SetNativeRecordByte5One reproduces 0x32975(index): it overwrites (rather
// than ORs) byte +0x05 of the selected 0x50-byte runtime record with 1. The
// byte's higher-level action meaning is intentionally not assigned here.
func SetNativeRecordByte5One(records []byte, index int) error {
	if index < 0 || index >= len(records)/nativeRecordSize {
		return fmt.Errorf("native record index %d is out of bounds", index)
	}
	records[index*nativeRecordSize+5] = 1
	return nil
}
