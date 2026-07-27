package battle

import (
	"encoding/binary"
	"errors"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

const NativeTransferVisible = 6

// RenderNativeTransferItemRows reproduces 0x2dc55 mode 1, used by 0x2f8ea.
// itemIDs is the caller's compact list of raw item bytes and start is the
// stateful even viewport origin owned by 0x2df6b.
func RenderNativeTransferItemRows(
	assets NativeItemPanelDataAssets,
	facilityCell fdother.RawCell,
	itemIDs []int,
	start, selected int,
	effectRows []byte,
	dst []byte,
) error {
	if len(dst) != nativeItemPanelBytes || len(itemIDs) == 0 ||
		start < 0 || start%2 != 0 || selected < start ||
		selected >= len(itemIDs) || selected >= start+NativeTransferVisible {
		return errors.New("battle: native transfer item rows/state are invalid")
	}
	visible := len(itemIDs) - start
	if visible > NativeTransferVisible {
		visible = NativeTransferVisible
	}
	staged := append([]byte(nil), dst...)
	for i := 0; i < visible; i++ {
		itemID := itemIDs[start+i]
		rowOffset := itemID * NativeItemEffectRowSize
		if itemID < 0 || rowOffset < 0 || rowOffset+NativeItemEffectRowSize > len(effectRows) {
			return fmt.Errorf("battle: native transfer item row %d is unavailable", itemID)
		}
		row := effectRows[rowOffset : rowOffset+NativeItemEffectRowSize]
		column, line := i%2, i/2
		x := 10 + 148*column
		y := 119 + 26*line
		category := 59
		switch {
		case row[0] < 0x15:
			category = 59
		case row[0] < 0x20:
			category = 60
		default:
			category = 61
		}
		if err := blitNativeItemPanelRawCell(
			assets.RawCells, category, staged, y*320+x,
		); err != nil {
			return err
		}
		foreground := byte(205)
		if start+i == selected {
			foreground = 201
		}
		if err := blitNativeItemPanelText(
			assets.Strings, assets.Font, staged,
			NativeItemPanelPoint{X: x + 28, Y: y + 3},
			itemID+181, foreground,
		); err != nil {
			return err
		}
		statIcon, statValue, hasValue := nativeTransferItemStat(row)
		if statIcon == 41 {
			if err := blitNativeItemPanelDigitFrame(
				assets.Frames, staged, NativeItemPanelPoint{X: x + 95, Y: y + 4}, 41,
			); err != nil {
				return err
			}
		} else {
			if err := blitNativeItemPanelRawCell(
				assets.RawCells, statIcon, staged, (y+2)*320+x+95,
			); err != nil {
				return err
			}
		}
		if hasValue {
			if err := blitNativeItemPanelNumber(
				assets.Frames, staged,
				NativeItemPanelPoint{X: x + 118, Y: y + 2},
				statValue, 42, 3,
			); err != nil {
				return err
			}
		}
		if err := facilityCell.BlitOpaqueAtOffset(
			staged, 320, (y+12)*320+x+95,
		); err != nil {
			return err
		}
		price := (3 * int(binary.LittleEndian.Uint16(row[19:21]))) >> 2
		if err := blitNativeItemPanelNumber(
			assets.Frames, staged,
			NativeItemPanelPoint{X: x + 104, Y: y + 12},
			price, 119, 5,
		); err != nil {
			return err
		}
	}
	copy(dst, staged)
	return nil
}

func nativeTransferItemStat(row []byte) (icon, value int, hasValue bool) {
	switch {
	case row[0] < 0x15:
		return 64, int(int16(binary.LittleEndian.Uint16(row[1:3]))), true
	case row[0] < 0x20:
		return 65, int(int16(binary.LittleEndian.Uint16(row[5:7]))), true
	case row[0] == 0x20 && row[13] == 5:
		return 66, int(int16(binary.LittleEndian.Uint16(row[14:16]))), true
	case row[0] == 0x20 && row[13] == 11:
		return 67, int(int16(binary.LittleEndian.Uint16(row[14:16]))), true
	default:
		return 41, 0, false
	}
}
