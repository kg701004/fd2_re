package fdother

import "fmt"

const (
	nativeUnitPresentStride     = 0x1c8
	nativeUnitPresentTilePixels = 0x18
	nativeUnitPresentBase       = 0x8088
)

// NativeUnitPresentByteOrigin is the exact destination address expression in
// 0x22470. The first LMI phase receives map coordinates x/y and writes at one
// tile row below the visible terrain origin. It returns a byte offset into the
// native 456-stride indexed work buffer rather than inventing a screen anchor.
// Negative results are retained: the original caller owns viewport validity.
func NativeUnitPresentByteOrigin(x, y, cameraX, cameraY int) int {
	return nativeUnitPresentBase +
		nativeUnitPresentTilePixels*(x-cameraX) +
		nativeUnitPresentTilePixels*nativeUnitPresentStride*(y-cameraY) +
		nativeUnitPresentStride
}

// UnitPresentStep is one native present boundary in 0x22253. It records only
// the resource/index/timing contract proven by the three callees; geometry,
// buffers and the intervening terrain/unit redraw are deliberately owned by a
// future indexed renderer adapter.
type UnitPresentStep struct {
	Phase      string
	Resource   int
	Entry      int
	DelayMs    int
	DelayTicks int
}

// NativeUnitPresentSchedule returns the 27 present boundaries of 0x22253:
// 0x22470's 11 FDOTHER#6 LMI cells, 0x22547's six FDOTHER#3 LUT remaps, and
// 0x22656's ten FDOTHER#3 LUT remaps. The two BIOS ticks after the middle
// phase are represented by DelayTicks on its last present, so their position
// cannot be accidentally moved before the sixth present.
func NativeUnitPresentSchedule() []UnitPresentStep {
	steps := make([]UnitPresentStep, 0, 27)
	for entry := 0x72; entry <= 0x7c; entry++ {
		steps = append(steps, UnitPresentStep{Phase: "lmi_intro", Resource: 6, Entry: entry, DelayTicks: 1})
	}
	for entry := 5; entry >= 0; entry-- {
		step := UnitPresentStep{Phase: "lut_contract", Resource: 3, Entry: entry, DelayMs: 10}
		if entry == 0 {
			step.DelayTicks = 2
		}
		steps = append(steps, step)
	}
	for entry := 0; entry <= 9; entry++ {
		steps = append(steps, UnitPresentStep{Phase: "lut_release", Resource: 3, Entry: entry, DelayTicks: 1})
	}
	return steps
}

// ValidateNativeUnitPresentSchedule rejects all approximations of the
// recovered 11+6+10 choreography. It is intended as a boundary check for an
// adapter before it mutates an indexed framebuffer.
func ValidateNativeUnitPresentSchedule(steps []UnitPresentStep) error {
	want := NativeUnitPresentSchedule()
	if len(steps) != len(want) {
		return fmt.Errorf("fdother: unit-present schedule has %d steps, want %d", len(steps), len(want))
	}
	for i := range want {
		if steps[i] != want[i] {
			return fmt.Errorf("fdother: unit-present step %d does not match native schedule", i)
		}
	}
	return nil
}
