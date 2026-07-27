package battle

import (
	"errors"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

const NativeReviveVisible = 3

// NativeReviveRow is one caller-resolved 0x30a47 candidate.
type NativeReviveRow struct {
	Sprite         fdicon.Sprite
	NameTextIndex  int
	RaceTextIndex  int
	ClassTextIndex int
	Fee            int
}

// RenderNativeReviveRows reproduces 0x30a47's three-row candidate renderer.
func RenderNativeReviveRows(
	assets NativeItemPanelDataAssets,
	currencyCell fdother.RawCell,
	rows []NativeReviveRow,
	selected int,
	dst []byte,
) error {
	if len(dst) != nativeItemPanelBytes || len(rows) == 0 ||
		len(rows) > NativeReviveVisible || selected < 0 || selected >= len(rows) {
		return errors.New("battle: native revive rows/state are invalid")
	}
	staged := append([]byte(nil), dst...)
	for i, row := range rows {
		if row.Fee < 0 || row.Fee > 0xffff {
			return fmt.Errorf("battle: native revive row %d fee is invalid", i)
		}
		if err := row.Sprite.BlitAt(staged, 320, 14, 117+26*i); err != nil {
			return fmt.Errorf("battle: native revive row %d sprite: %w", i, err)
		}
		foreground := byte(205)
		if i == selected {
			foreground = 201
		}
		y := 121 + 26*i
		for _, text := range []struct {
			x, index int
		}{
			{40, row.NameTextIndex},
			{130, row.RaceTextIndex},
			{175, row.ClassTextIndex},
		} {
			if err := blitNativeItemPanelText(
				assets.Strings, assets.Font, staged,
				NativeItemPanelPoint{X: text.x, Y: y},
				text.index, foreground,
			); err != nil {
				return fmt.Errorf("battle: native revive row %d text %d: %w", i, text.index, err)
			}
		}
		if err := currencyCell.BlitOpaqueAtOffset(staged, 320, (y+4)*320+220); err != nil {
			return fmt.Errorf("battle: native revive row %d currency: %w", i, err)
		}
		if err := blitNativeItemPanelNumber(
			assets.Frames, staged,
			NativeItemPanelPoint{X: 228, Y: y + 4},
			row.Fee, 119, 5,
		); err != nil {
			return fmt.Errorf("battle: native revive row %d fee: %w", i, err)
		}
	}
	copy(dst, staged)
	return nil
}
