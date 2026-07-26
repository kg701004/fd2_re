package fdother

import "fmt"

// IndexedTransitionPass is one verified 0x22046 choreography inside the
// 0x24618 transition. The two radial LUT passes are deliberately separate:
// native calls 0x219ad, redraws camera-relative objects through 0x127a9, then
// calls 0x219ad again and performs a final centered rectangular LUT pass.
// Callers own the descriptor/buffer source and may supply the redraw callback.
type IndexedTransitionPass struct {
	FirstRadial  RadialLUTRemap
	SecondRadial RadialLUTRemap
	FinalRect    CenteredRectLUTRemap
}

// ApplyIndexedTransitionPass executes one raw indexed pass atomically with
// respect to validation: all three geometries are checked before the first
// byte is changed. redraw is required because the native middle redraw is a
// mutating stage, not optional bookkeeping; a nil callback fails closed.
func ApplyIndexedTransitionPass(dst []byte, stride int, lut []byte, pass IndexedTransitionPass, redraw func([]byte) error) error {
	if redraw == nil {
		return fmt.Errorf("indexed transition: missing native middle redraw callback")
	}
	if err := validateRadialGeometry(dst, stride, lut, pass.FirstRadial); err != nil {
		return err
	}
	if err := validateRadialGeometry(dst, stride, lut, pass.SecondRadial); err != nil {
		return err
	}
	if err := validateRectGeometry(dst, stride, lut, pass.FinalRect); err != nil {
		return err
	}
	if err := ApplyRadialLUTRemap(dst, stride, lut, pass.FirstRadial); err != nil {
		return err
	}
	if err := redraw(dst); err != nil {
		return err
	}
	if err := ApplyRadialLUTRemap(dst, stride, lut, pass.SecondRadial); err != nil {
		return err
	}
	return ApplyCenteredRectLUTRemap(dst, stride, lut, pass.FinalRect)
}

func validateRadialGeometry(dst []byte, stride int, lut []byte, spec RadialLUTRemap) error {
	// Reuse the production operation's complete bounds checks without mutating
	// a caller buffer: a one-byte scratch is enough only after geometry is
	// independently checked, so keep this explicit and side-effect free.
	if len(lut) != 256 || stride <= 0 || spec.ClipWidth <= 0 || spec.ClipWidth > stride || spec.CenterX < 0 || spec.CenterX >= spec.ClipWidth || spec.CenterY < 0 || spec.Radius <= 0 || spec.Radius > 0x7fff || spec.Scale < 0 || spec.Scale > 0x7fff || spec.StartY < 0 || spec.EndY < spec.StartY || spec.EndY > len(dst)/stride {
		return fmt.Errorf("indexed transition: invalid radial geometry")
	}
	return nil
}

func validateRectGeometry(dst []byte, stride int, lut []byte, spec CenteredRectLUTRemap) error {
	if len(lut) != 256 || stride <= 0 || spec.ClipWidth <= 0 || spec.ClipWidth > stride || spec.CenterX < 0 || spec.CenterX >= spec.ClipWidth || spec.HorizontalRadius < 0 || spec.HorizontalRadius > 0x7fff || spec.StartY < 0 || spec.EndY < spec.StartY || spec.EndY > len(dst)/stride {
		return fmt.Errorf("indexed transition: invalid centered geometry")
	}
	return nil
}
