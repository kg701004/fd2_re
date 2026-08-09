package fdsave

// NativeBIOSKeyboardState preserves the two words accessed by the fixed
// FD2.EXE keyboard helpers.  The addresses are deliberately part of the
// field names: the original binary proves the word operations, but the
// remake does not promote them to a key code, event queue, or gameplay name.
//
// FD2.EXE linear addresses (fixed reference hash):
//   - 0x10620 compares word 0x41a with word 0x41c.
//   - 0x4e031 copies word 0x41a to word 0x41c.
type NativeBIOSKeyboardState struct {
	Word041A uint16
	Word041C uint16
}

// WordsDiffer is the exact boolean predicate emitted by 0x10620.  It does
// not decode the word values or claim which physical key produced them.
func (s NativeBIOSKeyboardState) WordsDiffer() bool {
	return s.Word041A != s.Word041C
}

// Copy041ATo041C applies the exact word write performed by 0x4e031.  The
// returned value reports whether the destination changed; callers must not
// interpret that as a consumed key or a gameplay event without a separate
// input trace and consumer contract.
func (s *NativeBIOSKeyboardState) Copy041ATo041C() bool {
	if s == nil || s.Word041A == s.Word041C {
		return false
	}
	s.Word041C = s.Word041A
	return true
}
