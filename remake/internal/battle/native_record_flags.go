package battle

import "fmt"

const nativeRecordSize = 0x50

// SetNativeRecordBit7 reproduces 0x13512(index): record[index*0x50+5] |=
// 0x80. The byte remains an offset-preserving raw flag; callers may project
// it to Unit.Acted only when their higher-level state has provenance.
func SetNativeRecordBit7(records []byte, index int) error {
	offset := index * nativeRecordSize
	if index < 0 || offset < 0 || offset+5 >= len(records) {
		return fmt.Errorf("native record index %d is out of bounds", index)
	}
	records[offset+5] |= 0x80
	return nil
}

// ClearNativeRecordBit7All reproduces 0x13536's full record scan.
func ClearNativeRecordBit7All(records []byte, count int) error {
	if count < 0 || len(records) < count*nativeRecordSize {
		return fmt.Errorf("native record buffer too short for %d records", count)
	}
	for index := 0; index < count; index++ {
		records[index*nativeRecordSize+5] &= 0x7f
	}
	return nil
}
