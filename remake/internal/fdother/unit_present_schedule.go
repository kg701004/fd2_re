package fdother

import (
	"errors"
	"fmt"
)

const (
	nativeUnitPresentStride     = 0x1c8
	nativeUnitPresentTilePixels = 0x18
	nativeUnitPresentBase       = 0x8088
	nativeUnitPresentWorkBytes  = 0x25680
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

// NativeUnitPresentContractStartY is 0x22547's middle-phase vertical boundary.
// An earlier adapter mislabeled this as a changing radius. Direct argument
// mapping into 0x22046 proves radius is the separate literal 11; native
// computes centerY=24*raw53ABD+15 and startY=trunc(centerY/5)*LUTIndex.
func NativeUnitPresentContractStartY(raw53ABD, lutIndex int) (int, error) {
	if lutIndex < 0 || lutIndex > 5 {
		return 0, errors.New("fdother: unit-present LUT index is outside 0..5")
	}
	return (24*raw53ABD + 15) / 5 * lutIndex, nil
}

// NativeUnitPresentLUTPass maps one 0x22547/0x22656 call into 0x22046's exact
// two-radial-plus-rectangle geometry. Both radial passes use radius 11 and
// scale 16. The first covers startY..192, the intervening redraw occurs, the
// second covers centerY..192, then the final width-34 rectangle covers
// startY..centerY. The visible width is the native 312-byte viewport.
func NativeUnitPresentLUTPass(centerX, centerY, startY int) (IndexedTransitionPass, error) {
	pass := IndexedTransitionPass{
		FirstRadial: RadialLUTRemap{
			CenterX: centerX, CenterY: centerY, Radius: 11, Scale: 16,
			StartY: startY, EndY: 192, ClipWidth: 312,
		},
		SecondRadial: RadialLUTRemap{
			CenterX: centerX, CenterY: centerY, Radius: 11, Scale: 16,
			StartY: centerY, EndY: 192, ClipWidth: 312,
		},
		FinalRect: CenteredRectLUTRemap{
			CenterX: centerX, HorizontalRadius: 17,
			StartY: startY, EndY: centerY, ClipWidth: 312,
		},
	}
	dst, lut := make([]byte, nativeUnitPresentStride*192), make([]byte, 256)
	if err := validateRadialGeometry(dst, nativeUnitPresentStride, lut, pass.FirstRadial); err != nil {
		return IndexedTransitionPass{}, fmt.Errorf("fdother: invalid unit-present first geometry: %w", err)
	}
	if err := validateRadialGeometry(dst, nativeUnitPresentStride, lut, pass.SecondRadial); err != nil {
		return IndexedTransitionPass{}, fmt.Errorf("fdother: invalid unit-present second geometry: %w", err)
	}
	if err := validateRectGeometry(dst, nativeUnitPresentStride, lut, pass.FinalRect); err != nil {
		return IndexedTransitionPass{}, fmt.Errorf("fdother: invalid unit-present rectangle geometry: %w", err)
	}
	return pass, nil
}

// BlitNativeUnitPresentLMI reproduces one 0x22470 LMI-cell write before that
// phase redraws units and presents the 320x192 viewport.  Native 0x4e85b
// decodes through 0x4e916 and preserves destination pixels when the decoded
// value is zero; LMI1Entry.BlitAt has that exact transparent rule.
//
// The caller supplies the full native work buffer (not a cropped viewport).
// Offscreen origins are rejected rather than emulating unchecked native memory
// writes; a future renderer must make its clipping policy explicit.
func BlitNativeUnitPresentLMI(entry LMI1Entry, dst []byte, x, y, cameraX, cameraY int) error {
	origin := NativeUnitPresentByteOrigin(x, y, cameraX, cameraY)
	if origin < 0 || origin >= len(dst) {
		return errors.New("fdother: unit-present LMI origin is outside destination")
	}
	return entry.BlitAt(dst, nativeUnitPresentStride, origin%nativeUnitPresentStride, origin/nativeUnitPresentStride, false)
}

// RunNativeUnitPresentLMIIntro executes 0x22470's first 11 presentation
// passes. Each FDOTHER#6 entry 0x72..0x7c is blitted at the same recovered
// destination, then redrawPresentTick must perform the native intervening
// unit redraw, 320x192 present, and one BIOS tick. Keeping that callback
// mandatory prevents this helper from silently collapsing the 11 presents.
func RunNativeUnitPresentLMIIntro(entries []LMI1Entry, dst []byte, x, y, cameraX, cameraY int, redrawPresentTick func() error) error {
	if len(entries) <= 0x7c || redrawPresentTick == nil {
		return errors.New("fdother: incomplete unit-present LMI intro adapter")
	}
	for index := 0x72; index <= 0x7c; index++ {
		if err := BlitNativeUnitPresentLMI(entries[index], dst, x, y, cameraX, cameraY); err != nil {
			return fmt.Errorf("fdother: unit-present LMI entry %#x: %w", index, err)
		}
		if err := redrawPresentTick(); err != nil {
			return fmt.Errorf("fdother: unit-present LMI entry %#x present: %w", index, err)
		}
	}
	return nil
}

// UnitPresentStep is one full-viewport 0x11eb0 present boundary in 0x22253.
// The separately recovered 18/24 progressive direct-VGA strip writes between
// contract and release are intentionally not collapsed into this list.
type UnitPresentStep struct {
	Phase      string
	Resource   int
	Entry      int
	DelayMs    int
	DelayTicks int
}

// NativeUnitPresentCall is 0x22253's five-argument ABI. VisualX/VisualY anchor
// the intro, contract and direct-VGA bridge. NewX/NewY are written to runtime
// unit+0/+1 only after contract. Native uses 0xff as the off-map mutation
// value; the visual anchor remains independently caller-supplied.
type NativeUnitPresentCall struct {
	UnitSlot         int
	NewX, NewY       byte
	VisualX, VisualY byte
}

// PlanNativeUnitPresentCall preserves the byte truncation boundary while
// rejecting values which an editable script could not have supplied through
// the recovered five integer arguments.
func PlanNativeUnitPresentCall(unitSlot, newX, newY, visualX, visualY int) (NativeUnitPresentCall, error) {
	for _, value := range []int{unitSlot, newX, newY, visualX, visualY} {
		if value < 0 || value > 0xff {
			return NativeUnitPresentCall{}, errors.New("fdother: unit-present call argument outside byte range")
		}
	}
	return NativeUnitPresentCall{
		UnitSlot: unitSlot,
		NewX:     byte(newX), NewY: byte(newY),
		VisualX: byte(visualX), VisualY: byte(visualY),
	}, nil
}

// UnitPresentLUTFrame is one of 0x22253's sixteen 0x22046 calls after the LMI
// intro. Raw53AB9/Raw53ABD remain address-derived inputs: the code proves
// their pixel-center arithmetic but not their higher-level gameplay names.
type UnitPresentLUTFrame struct {
	Phase      string
	LUTIndex   int
	Pass       IndexedTransitionPass
	DelayMs    int
	DelayTicks int
}

// NativeUnitPresentLUTFrames materializes the exact six contract and ten
// release geometries. Contract frames move the first-pass/rectangle start
// boundary by floor(centerY/5)*index; release frames always start at row 0.
func NativeUnitPresentLUTFrames(raw53AB9, raw53ABD int) ([]UnitPresentLUTFrame, error) {
	centerX, centerY := 24*raw53AB9+12, 24*raw53ABD+15
	frames := make([]UnitPresentLUTFrame, 0, 16)
	for index := 5; index >= 0; index-- {
		startY, err := NativeUnitPresentContractStartY(raw53ABD, index)
		if err != nil {
			return nil, err
		}
		pass, err := NativeUnitPresentLUTPass(centerX, centerY, startY)
		if err != nil {
			return nil, err
		}
		frame := UnitPresentLUTFrame{
			Phase: "lut_contract", LUTIndex: index, Pass: pass, DelayMs: 10,
		}
		if index == 0 {
			frame.DelayTicks = 2
		}
		frames = append(frames, frame)
	}
	for index := 0; index < 10; index++ {
		pass, err := NativeUnitPresentLUTPass(centerX, centerY, 0)
		if err != nil {
			return nil, err
		}
		frames = append(frames, UnitPresentLUTFrame{
			Phase: "lut_release", LUTIndex: index, Pass: pass, DelayTicks: 1,
		})
	}
	return frames, nil
}

// RunNativeUnitPresentLUTFrame reproduces one 0x22547/0x22656 buffer
// transaction. Native restores all 0x25680 bytes before every frame, applies
// 0x22046 at work+0x8088 with a mandatory object redraw between radial passes,
// then presents. Callbacks receive the complete work buffer, not a cropped
// viewport, so sprite redraw cannot accidentally target a detached slice.
func RunNativeUnitPresentLUTFrame(
	work, snapshot, lut []byte,
	frame UnitPresentLUTFrame,
	redraw func([]byte) error,
	present func([]byte, UnitPresentLUTFrame) error,
) error {
	if len(work) != nativeUnitPresentWorkBytes || len(snapshot) != nativeUnitPresentWorkBytes {
		return errors.New("fdother: unit-present work/snapshot must be exactly 0x25680 bytes")
	}
	if len(lut) != 256 || redraw == nil || present == nil {
		return errors.New("fdother: incomplete unit-present LUT frame adapter")
	}
	copy(work, snapshot)
	view := work[nativeUnitPresentBase:]
	if err := ApplyIndexedTransitionPass(
		view, nativeUnitPresentStride, lut, frame.Pass,
		func([]byte) error { return redraw(work) },
	); err != nil {
		return fmt.Errorf("fdother: unit-present %s LUT %d: %w", frame.Phase, frame.LUTIndex, err)
	}
	if err := present(work, frame); err != nil {
		return fmt.Errorf("fdother: unit-present %s LUT %d present: %w", frame.Phase, frame.LUTIndex, err)
	}
	return nil
}

// NativeUnitPresentSchedule returns the 27 full-viewport present boundaries:
// 0x22470's 11 FDOTHER#6 LMI cells, 0x22547's six FDOTHER#3 LUT remaps, and
// 0x22656's ten FDOTHER#3 LUT remaps. The two BIOS ticks after the middle
// phase are represented by DelayTicks on its last present, so their position
// cannot be accidentally moved before the sixth present. The middle direct
// VGA bridge adds 18 or 24 observable row writes and is owned by indexedmap.
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
