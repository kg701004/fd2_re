package battle

import "fmt"

// RewriteNativeMarker1F reproduces the raw loop at 0x24e80: beginning at
// runtime slot 0x10 and stopping before caller-supplied count, records whose
// byte +0x07 equals 0x1f receive bytes +0=0x10 and +1=0x06. These bytes remain
// unnamed; the helper deliberately exposes only the proven mutation.
func RewriteNativeMarker1F(records []byte, count int) error {
	if count < 0 || count > len(records)/nativeRecordSize {
		return fmt.Errorf("native marker rewrite count %d is outside record buffer", count)
	}
	if count > 0x10 && len(records) < count*nativeRecordSize {
		return fmt.Errorf("native marker rewrite needs %d bytes, got %d", count*nativeRecordSize, len(records))
	}
	for index := 0x10; index < count; index++ {
		base := index * nativeRecordSize
		if records[base+0x07] == 0x1f {
			records[base] = 0x10
			records[base+1] = 0x06
		}
	}
	return nil
}
