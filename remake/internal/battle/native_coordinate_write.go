package battle

// SetNativeUnitCoordinateBytes reproduces the state write in 0x22253 used by
// command-23 relocation: the final native coordinates are written to raw
// record bytes +0 and +1.  Indexed renderer/presentation work is outside this
// byte-level adapter.
func SetNativeUnitCoordinateBytes(records []byte, unitIndex int, x, y byte) error {
	base := unitIndex * nativeRecordSize
	if unitIndex < 0 || base < 0 || base+2 > len(records) {
		return recordBoundsError(unitIndex)
	}
	records[base], records[base+1] = x, y
	return nil
}
