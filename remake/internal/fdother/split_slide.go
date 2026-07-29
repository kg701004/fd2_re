package fdother

import "errors"

// NativeBattleEntrySplitSlideStep is one verified 0x1f42d pass reached from
// 0x1a30b's battle-entry indexed choreography. The archive cell and any
// player-facing label remain separate: native code proves only these indexed
// placements, not a preparation-selection-window animation.
type NativeBattleEntrySplitSlideStep struct {
	Offset         int
	LeftX, LeftY   int
	RightX, RightY int
}

// NativeBattleEntrySplitSlideSteps returns the exact five-pass order used by
// 0x1f1cc and reversed by 0x1f30a. Coordinates are in the 456-byte indexed
// battle surface.
func NativeBattleEntrySplitSlideSteps() []NativeBattleEntrySplitSlideStep {
	offsets := [...]int{100, 75, 50, 25, 0}
	steps := make([]NativeBattleEntrySplitSlideStep, len(offsets))
	for i, offset := range offsets {
		steps[i] = NativeBattleEntrySplitSlideStep{
			Offset: offset,
			LeftX:  85 - offset, LeftY: 82,
			RightX: 165 + offset, RightY: 81,
		}
	}
	return steps
}

// BlitNativeBattleEntrySplitSlideCell executes one native cell pass.
func BlitNativeBattleEntrySplitSlideCell(cell LMI1Entry, step NativeBattleEntrySplitSlideStep, dst []byte, stride int) error {
	if stride != 456 {
		return errors.New("fdother: native split slide requires stride 456")
	}
	if err := cell.BlitAtClipped(dst, stride, step.LeftX, step.LeftY, false); err != nil {
		return err
	}
	return cell.BlitAtClipped(dst, stride, step.RightX, step.RightY, false)
}

// RunNativeBattleEntrySplitSlide executes the verified five-pass choreography.
// Present and restore remain callbacks because their native VGA/tick
// implementations are caller-owned and have not been generalized.
func RunNativeBattleEntrySplitSlide(cell LMI1Entry, dst []byte, present func() error, restore func() error) error {
	if present == nil || restore == nil {
		return errors.New("fdother: native split slide callbacks are required")
	}
	for _, step := range NativeBattleEntrySplitSlideSteps() {
		if err := BlitNativeBattleEntrySplitSlideCell(cell, step, dst, 456); err != nil {
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
