package fdother

import "errors"

// NativeSplitSlideStep is one verified 0x1f42d/0x1f1cc preparation slide
// pass.  The archive cell and its semantic label are deliberately separate:
// native code only proves these indexed placements.
type NativeSplitSlideStep struct {
	Offset         int
	LeftX, LeftY   int
	RightX, RightY int
}

// NativeSplitSlideSteps returns the exact five-pass order used by the native
// opening path.  Coordinates are in the 456-byte indexed off-screen surface.
func NativeSplitSlideSteps() []NativeSplitSlideStep {
	offsets := [...]int{100, 75, 50, 25, 0}
	steps := make([]NativeSplitSlideStep, len(offsets))
	for i, offset := range offsets {
		steps[i] = NativeSplitSlideStep{
			Offset: offset,
			LeftX:  85 - offset, LeftY: 82,
			RightX: 165 + offset, RightY: 81,
		}
	}
	return steps
}

// BlitNativeSplitSlideCell executes one native cell pass.  It accepts the
// caller's destination surface and explicit step; it does not infer which UI
// field the cell represents.
func BlitNativeSplitSlideCell(cell LMI1Entry, step NativeSplitSlideStep, dst []byte, stride int) error {
	if stride != 456 {
		return errors.New("fdother: native split slide requires stride 456")
	}
	if err := cell.BlitAtClipped(dst, stride, step.LeftX, step.LeftY, false); err != nil {
		return err
	}
	return cell.BlitAtClipped(dst, stride, step.RightX, step.RightY, false)
}

// RunNativeSplitSlide executes the verified five-pass choreography.  Present
// and restore remain callbacks because their native VGA/tick implementations
// are caller-owned and have not been generalized.
func RunNativeSplitSlide(cell LMI1Entry, dst []byte, present func() error, restore func() error) error {
	if present == nil || restore == nil {
		return errors.New("fdother: native split slide callbacks are required")
	}
	for _, step := range NativeSplitSlideSteps() {
		if err := BlitNativeSplitSlideCell(cell, step, dst, 456); err != nil {
			return err
		}
		if err := present(); err != nil {
			return err
		}
		if err := restore(); err != nil {
			return err
		}
	}
	return nil
}
