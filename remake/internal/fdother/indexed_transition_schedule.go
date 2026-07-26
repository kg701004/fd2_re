package fdother

import "fmt"

// NativeIndexedTransitionFrame preserves one 0x24618 strip pass. LUTIndex is
// the raw FDOTHER#3 selector (the native loop visits 9..1); Radius is the
// caller-supplied third argument advanced by the fourth argument.
type NativeIndexedTransitionFrame struct {
	Pass         int
	LUTIndex     int
	Radius       int
	FrameDelayMs int
}

// NativeIndexedTransitionSchedule is the timing/data boundary around the
// 0x24618 compositor. It deliberately stops before LUT loading,
// double-buffer mutation, redraw, and VGA/Ebiten presentation.
type NativeIndexedTransitionSchedule struct {
	Frames         []NativeIndexedTransitionFrame
	TailDelayMs    int
	PaletteDeltas  []int
	PaletteDelayMs int
}

// BuildNativeIndexedTransitionSchedule reproduces the exact loop bounds and
// progression in 0x24618: nine passes (LUT index 9 down to 1), then a 500ms
// hold and palette deltas 0..62 inclusive by 2 at 4ms each.
func BuildNativeIndexedTransitionSchedule(startRadius, radiusStep int) (NativeIndexedTransitionSchedule, error) {
	if startRadius < 0 || startRadius > 0x7fff || radiusStep < -0x7fff || radiusStep > 0x7fff {
		return NativeIndexedTransitionSchedule{}, fmt.Errorf("native indexed transition: invalid radius args %d,%d", startRadius, radiusStep)
	}
	frames := make([]NativeIndexedTransitionFrame, 0, 9)
	radius := startRadius
	for pass, descriptor := 0, 9; descriptor > 0; pass, descriptor = pass+1, descriptor-1 {
		frames = append(frames, NativeIndexedTransitionFrame{Pass: pass, LUTIndex: descriptor, Radius: radius, FrameDelayMs: 5})
		radius += radiusStep
	}
	deltas := make([]int, 0, 32)
	for delta := 0; delta <= 62; delta += 2 {
		deltas = append(deltas, delta)
	}
	return NativeIndexedTransitionSchedule{Frames: frames, TailDelayMs: 500, PaletteDeltas: deltas, PaletteDelayMs: 4}, nil
}
