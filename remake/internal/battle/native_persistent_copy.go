package battle

import (
	"encoding/binary"
	"fmt"
)

// ApplyNativePersistentRecordCopy reproduces the mutation core of 0x11506
// after its caller has selected a runtime/persistent pair. It copies one
// 0x50-byte runtime record to persistent storage, clears persistent +0x22..27,
// preserves only byte +0x05 bit0, then copies +0x46 to +0x44 and (unless the
// preserved byte equals 1) copies +0x42 to +0x40. The unknown 0x3453e
// zero-identity gate and 0x1145a tail are intentionally caller-owned.
func ApplyNativePersistentRecordCopy(runtime, persistent []byte, runtimeIndex, persistentIndex int) error {
	runtimeBase, err := nativePersistentRecordBase(runtime, runtimeIndex)
	if err != nil {
		return fmt.Errorf("runtime: %w", err)
	}
	persistentBase, err := nativePersistentRecordBase(persistent, persistentIndex)
	if err != nil {
		return fmt.Errorf("persistent: %w", err)
	}
	var record [nativeRecordSize]byte
	copy(record[:], runtime[runtimeBase:runtimeBase+nativeRecordSize])
	copy(persistent[persistentBase:persistentBase+nativeRecordSize], record[:])
	persistentRecord := persistent[persistentBase : persistentBase+nativeRecordSize]
	for i := 0x22; i <= 0x27; i++ {
		persistentRecord[i] = 0
	}
	persistentRecord[5] &= 1
	if persistentRecord[5] != 1 {
		binary.LittleEndian.PutUint16(persistentRecord[0x40:0x42], binary.LittleEndian.Uint16(persistentRecord[0x42:0x44]))
	}
	binary.LittleEndian.PutUint16(persistentRecord[0x44:0x46], binary.LittleEndian.Uint16(persistentRecord[0x46:0x48]))
	return nil
}

func nativePersistentRecordBase(records []byte, index int) (int, error) {
	base := index * nativePersistentRecordSize
	if index < 0 || base < 0 || base+nativePersistentRecordSize > len(records) {
		return 0, fmt.Errorf("record index %d is out of bounds", index)
	}
	return base, nil
}
