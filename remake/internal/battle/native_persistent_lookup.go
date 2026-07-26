package battle

import "fmt"

const nativePersistentRecordSize = nativeRecordSize

// FindNativePersistentIdentity reproduces the byte-level lookup shared by
// 0x24bde/0x33499: scan the caller-supplied persistent record count, using
// record stride 0x50 and comparing the unsigned byte at record+0x08. It
// returns the first raw record index and never changes the buffer.
func FindNativePersistentIdentity(records []byte, count int, identity byte) (int, bool, error) {
	if count < 0 || count > 32 {
		return -1, false, fmt.Errorf("native persistent record count %d is outside 0..32", count)
	}
	if len(records) < count*nativePersistentRecordSize {
		return -1, false, fmt.Errorf("native persistent records need %d bytes, got %d", count*nativePersistentRecordSize, len(records))
	}
	for index := 0; index < count; index++ {
		if records[index*nativePersistentRecordSize+0x08] == identity {
			return index, true, nil
		}
	}
	return -1, false, nil
}
