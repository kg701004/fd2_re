package fdother

import "errors"

const (
	// NativeCh23StageStride/Height are the raw 0x53AFF staging geometry used by
	// 0x24D22 and the dword_53C03==23 branch of 0x11EEE.
	NativeCh23StageStride = 312
	NativeCh23StageWidth  = 312
	NativeCh23StageHeight = 192
)

// nativeCh23PaletteCycle is the fixed 31×RGB byte window at linear 0x60003
// used by 0x4DFCC.  The helper selects a byte offset of 3*byte_60002 and
// writes the next 16 RGB triples to DAC indexes 0x20..0x2f. Values are six-bit
// VGA components copied from the fixed FD2.EXE, not inferred from a screenshot.
var nativeCh23PaletteCycle = [31][3]byte{
	{0x0e, 0x15, 0x26}, {0x0d, 0x14, 0x25}, {0x0d, 0x14, 0x25}, {0x0d, 0x14, 0x25},
	{0x0c, 0x13, 0x24}, {0x0c, 0x13, 0x24}, {0x0b, 0x12, 0x23}, {0x0b, 0x12, 0x23},
	{0x0b, 0x12, 0x23}, {0x0b, 0x12, 0x23}, {0x0c, 0x13, 0x24}, {0x0c, 0x13, 0x24},
	{0x0d, 0x14, 0x25}, {0x0e, 0x15, 0x26}, {0x0e, 0x15, 0x26},
	{0x0e, 0x15, 0x26}, {0x0d, 0x14, 0x25}, {0x0d, 0x14, 0x25}, {0x0d, 0x14, 0x25},
	{0x0c, 0x13, 0x24}, {0x0c, 0x13, 0x24}, {0x0b, 0x12, 0x23}, {0x0b, 0x12, 0x23},
	{0x0b, 0x12, 0x23}, {0x0b, 0x12, 0x23}, {0x0c, 0x13, 0x24}, {0x0c, 0x13, 0x24},
	{0x0d, 0x14, 0x25}, {0x0e, 0x15, 0x26}, {0x0e, 0x15, 0x26}, {0x0e, 0x15, 0x26},
}

// RotateNativeCh23Rows reproduces the arg==0 row-copy branch of 0x24D22.
// The last latch rows wrap to the top; all other rows move down by latch.
// Invalid input is rejected before the destination changes, preserving the
// raw helper's bounded gate.
func RotateNativeCh23Rows(buffer []byte, latch int) error {
	if len(buffer) < NativeCh23StageStride*NativeCh23StageHeight ||
		latch < 0 || latch > NativeCh23StageHeight {
		return errors.New("fdother: invalid ch23 staging latch")
	}
	if latch == 0 {
		return nil
	}
	top := append([]byte(nil), buffer[(NativeCh23StageHeight-latch)*NativeCh23StageStride:NativeCh23StageHeight*NativeCh23StageStride]...)
	for row := NativeCh23StageHeight - latch - 1; row >= 0; row-- {
		src := row * NativeCh23StageStride
		dst := (row + latch) * NativeCh23StageStride
		copy(buffer[dst:dst+NativeCh23StageWidth], buffer[src:src+NativeCh23StageWidth])
	}
	copy(buffer[:latch*NativeCh23StageStride], top)
	return nil
}

// ApplyNativeCh23PaletteCycle reproduces 0x4DFCC's 16-entry DAC write.  It
// changes only palette indexes 0x20..0x2f and leaves every other entry intact.
// The phase is the raw byte_60002 value and must be in 0..15.
func ApplyNativeCh23PaletteCycle(dac []byte, phase int) error {
	if len(dac) != 256*3 || phase < 0 || phase > 15 {
		return errors.New("fdother: invalid ch23 palette-cycle input")
	}
	next := append([]byte(nil), dac...)
	for i := 0; i < 16*3; i++ {
		rgb := nativeCh23PaletteCycle[(phase*3+i)/3][(phase*3+i)%3]
		next[0x20*3+i] = rgb
	}
	copy(dac, next)
	return nil
}
