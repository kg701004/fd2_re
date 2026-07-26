package fdother

// NativeRNGStep reproduces 0x4e893's 16-bit state transition:
// state = rol16(state + 0x9014, 3).  The native callers use the remainder
// after division by four as a raw marker source, not the quotient.
func NativeRNGStep(state uint16) uint16 {
	state += 0x9014
	return state<<3 | state>>13
}

// NativeRNGMarker is the exact marker byte produced by the growth callers
// after idiv 4: EDX remainder + 2.
func NativeRNGMarker(state uint16) byte {
	return byte(NativeRNGStep(state)%4 + 2)
}
