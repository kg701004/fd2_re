package battle

import (
	"errors"
	"fmt"
)

// RenderNativeCommandOverlay reproduces 0x1ceed over an already composed
// 0x17eef/0x17fc0 panel. Commands remain in 0x1c269 bit order; no normalized
// spell list or effect semantics are consulted.
func RenderNativeCommandOverlay(
	assets NativeItemPanelDataAssets,
	commandIDs []int,
	book []NativeCommandRecord,
	unit *Unit,
	selected int,
	dst []byte,
) error {
	if len(dst) != nativeItemPanelBytes || selected < -1 || selected >= len(commandIDs) {
		return errors.New("battle: native command overlay inputs are invalid")
	}
	// QoL deviation (user request): the original local buffer only ever held
	// up to 32 slots because no native unit ever set more than a handful of
	// command bits. NativeCommandRecordCount(36) is the true ceiling now
	// that a unit can hold every defined command; anything beyond that is
	// still rejected as a genuine data error.
	if len(commandIDs) > NativeCommandRecordCount {
		return errors.New("battle: native command overlay exceeds local command buffer")
	}
	windowSel := selected
	if windowSel < 0 {
		windowSel = 0
	}
	if len(commandIDs) > 0 {
		start, visible := NativeCommandGridWindow(len(commandIDs), windowSel, 0)
		commandIDs = commandIDs[start:start+visible]
		if selected >= 0 {
			selected -= start
		}
	}
	staged := append([]byte(nil), dst...)
	for i, commandID := range commandIDs {
		if commandID < 0 || commandID >= len(book) || book[commandID].ID != commandID {
			return fmt.Errorf("battle: native command record %d is unavailable", commandID)
		}
		column, row := i/4, i%4
		x, y := 18+100*column, 103+22*row
		foreground := byte(205)
		if i == selected {
			foreground = 201
		}
		if err := blitNativeItemPanelText(
			assets.Strings, assets.Font, staged,
			NativeItemPanelPoint{X: x, Y: y},
			441+commandID, foreground,
		); err != nil {
			return fmt.Errorf("battle: native command %d label: %w", commandID, err)
		}
		if err := blitNativeItemPanelRawCell(
			assets.RawCells, 92, staged, (y+5)*320+x+50,
		); err != nil {
			return fmt.Errorf("battle: native command %d MP icon: %w", commandID, err)
		}
		if err := blitNativeItemPanelNumber(
			assets.Frames, staged,
			NativeItemPanelPoint{X: x + 73, Y: y + 5},
			NativeCommandMPCostFor(unit, book[commandID].MPCost), 42, 2,
		); err != nil {
			return fmt.Errorf("battle: native command %d MP cost: %w", commandID, err)
		}
	}
	copy(dst, staged)
	return nil
}
