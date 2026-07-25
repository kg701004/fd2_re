package fdother

import (
	"errors"
	"math"
)

// RadialLUTRemap is the recovered geometry ABI of FD2.EXE 0x219ad. It is
// intentionally an indexed-buffer primitive: callers own descriptor loading,
// buffer presentation, and timing. ClipWidth is the native visible row width
// (0x138 for the callers recovered so far), which may be smaller than stride.
type RadialLUTRemap struct {
	CenterX, CenterY int
	Radius, Scale    int
	StartY, EndY     int // EndY is exclusive.
	ClipWidth        int
}

// CenteredRectLUTRemap is the final LUT-only pass in FD2.EXE 0x22046. Its
// horizontal radius is already recovered by its caller as
// trunc(native_radius*1.6); unlike RadialLUTRemap it does not infer that
// conversion or absorb the intervening 0x127a9 redraw between native passes.
type CenteredRectLUTRemap struct {
	CenterX, HorizontalRadius int
	StartY, EndY              int // EndY is exclusive.
	ClipWidth                 int
}

// ApplyRadialLUTRemap applies 0x219ad's in-place palette-index remap.
//
// Native uses 0x4db9c(lut, count, pixels), so every selected source byte is
// replaced with lut[source]. For each row strictly inside CenterY±Radius it
// maps the clipped interval CenterX±trunc(sqrt(radius²-dy²)*scale/10).
// The original invokes __CHP (0x377a4), whose temporary x87 control word
// selects toward-zero rounding; all quantities here are non-negative, so the
// recovered result is the mathematical floor.
func ApplyRadialLUTRemap(dst []byte, stride int, lut []byte, spec RadialLUTRemap) error {
	if len(lut) != 256 {
		return errors.New("fdother: LUT must have 256 entries")
	}
	if stride <= 0 || spec.ClipWidth <= 0 || spec.ClipWidth > stride || spec.CenterX < 0 || spec.CenterX >= spec.ClipWidth || spec.CenterY < 0 || spec.Radius <= 0 || spec.Radius > 0x7fff || spec.Scale < 0 || spec.Scale > 0x7fff || spec.StartY < 0 || spec.EndY < spec.StartY || spec.EndY > len(dst)/stride {
		return errors.New("fdother: invalid radial LUT remap geometry")
	}
	for y := spec.StartY; y < spec.EndY; y++ {
		dy := spec.CenterY - y
		if dy < 0 {
			dy = -dy
		}
		// 0x219ad's jle/jge leaves the two radius boundary rows untouched.
		if dy >= spec.Radius {
			continue
		}
		span := int(math.Sqrt(float64(spec.Radius*spec.Radius-dy*dy)) * float64(spec.Scale) / 10)
		left, right := spec.CenterX-span, spec.CenterX+span
		if left < 0 {
			left = 0
		}
		if right > spec.ClipWidth {
			right = spec.ClipWidth
		}
		row := dst[y*stride : y*stride+spec.ClipWidth]
		for x := left; x < right; x++ {
			row[x] = lut[row[x]]
		}
	}
	return nil
}

// ApplyCenteredRectLUTRemap applies 0x22046's final in-place LUT pass over a
// clipped centered horizontal interval on each requested row. It is separate
// from the two radial passes because 0x22046 invokes an opaque redraw between
// them; callers must not accidentally claim the whole native choreography.
func ApplyCenteredRectLUTRemap(dst []byte, stride int, lut []byte, spec CenteredRectLUTRemap) error {
	if len(lut) != 256 {
		return errors.New("fdother: LUT must have 256 entries")
	}
	if stride <= 0 || spec.ClipWidth <= 0 || spec.ClipWidth > stride || spec.CenterX < 0 || spec.CenterX >= spec.ClipWidth || spec.HorizontalRadius < 0 || spec.HorizontalRadius > 0x7fff || spec.StartY < 0 || spec.EndY < spec.StartY || spec.EndY > len(dst)/stride {
		return errors.New("fdother: invalid centered LUT rectangle")
	}
	left, right := spec.CenterX-spec.HorizontalRadius, spec.CenterX+spec.HorizontalRadius
	if left < 0 {
		left = 0
	}
	if right > spec.ClipWidth {
		right = spec.ClipWidth
	}
	for y := spec.StartY; y < spec.EndY; y++ {
		row := dst[y*stride : y*stride+spec.ClipWidth]
		for x := left; x < right; x++ {
			row[x] = lut[row[x]]
		}
	}
	return nil
}
