package fdother

// NativePreparationInputResult is the raw return contract of 0x19953.
type NativePreparationInputResult int

const (
	NativePreparationInputContinue NativePreparationInputResult = 0
	NativePreparationInputConfirm  NativePreparationInputResult = 1
	NativePreparationInputCancel   NativePreparationInputResult = -1
)

// ApplyNativePreparationInput applies one verified scancode branch.  The
// cursor state is the raw [0x53c57] 0/1 value; confirm/cancel reset it to zero
// exactly as native code does. Unknown keys remain a wait/continue result.
func ApplyNativePreparationInput(scanCode byte, cursorState *int) NativePreparationInputResult {
	if cursorState == nil {
		return NativePreparationInputContinue
	}
	switch scanCode {
	case 0xe0, 0x52, 0x1c, 0x39:
		*cursorState = 0
		return NativePreparationInputConfirm
	case 0x01, 0x53:
		*cursorState = 0
		return NativePreparationInputCancel
	case 0x4b:
		*cursorState = 0
	case 0x4d:
		*cursorState = 1
	}
	return NativePreparationInputContinue
}
