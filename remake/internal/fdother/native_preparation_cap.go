package fdother

// NativePreparationPartyLimit reproduces 0x318ad's raw cap gate: the native
// chapter/index global is compared against 0x1a, yielding cap 15 through 26
// and cap 19 above it. The argument is a native index, not a display chapter.
func NativePreparationPartyLimit(nativeIndex int) int {
	if nativeIndex > 0x1a {
		return 19
	}
	return 15
}
