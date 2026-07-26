package battle

import "fmt"

// NativeRecordByte5Bit0 reproduces 0x3453e(index): return the selected
// runtime record byte +0x05 masked with bit0. It is a raw predicate only; no
// acted/alive/active name is assigned.
func NativeRecordByte5Bit0(records []byte, index int) (byte, error) {
	if index < 0 || index >= len(records)/nativeRecordSize {
		return 0, fmt.Errorf("native record index %d is out of bounds", index)
	}
	return records[index*nativeRecordSize+5] & 1, nil
}
