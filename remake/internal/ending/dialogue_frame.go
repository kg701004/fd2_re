package ending

import (
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

// RenderDialogueFrameGrid executes only the recovered 0x168b6→0x4e9bb raw
// cell copies into the caller's portrait restore buffer. It does not render
// text, DATO, input, or any semantic UI layer.
func RenderDialogueFrameGrid(m Montage, cells []fdother.RawCell, dst []byte) error {
	if len(dst) != Bytes {
		return fmt.Errorf("ending: dialogue frame destination must be %d bytes", Bytes)
	}
	placements, err := m.PlanDialogueFrameGrid()
	if err != nil {
		return err
	}
	for _, placement := range placements {
		if placement.ResourceIndex < 0 || placement.ResourceIndex >= len(cells) {
			return fmt.Errorf("ending: dialogue frame resource index %d is unavailable", placement.ResourceIndex)
		}
		if err := cells[placement.ResourceIndex].BlitOpaqueAtOffset(dst, m.PartyCycle.DialogueFrameLayout.Stride, placement.DestinationByte); err != nil {
			return fmt.Errorf("ending: dialogue frame resource %d at %#x: %w", placement.ResourceIndex, placement.DestinationByte, err)
		}
	}
	return nil
}
