package fdicon

import "errors"

// NativeTerrainFrameIndex reproduces 0x11eee's FDSHAP descriptor selector.
// tile is the composition word's low 10 bits; flags is the selected terrain
// control byte. flip is native 0x53a40 (0 or 1), and cycle is 0x53c0b.
// Flag priority is 0x08, then 0x10, then 0x04, then the base tile.
func NativeTerrainFrameIndex(tile int, flags byte, flip, cycle int) (int, error) {
	if tile < 0 || tile > 0x3ff || (flip != 0 && flip != 1) {
		return 0, errors.New("fdicon: invalid native terrain frame selector")
	}
	if flags&0x08 != 0 {
		return tile + 2*flip, nil
	}
	if flags&0x10 != 0 {
		return tile + truncDiv2(cycle), nil
	}
	if flags&0x04 != 0 {
		return tile + flip, nil
	}
	return tile, nil
}

func truncDiv2(v int) int {
	if v < 0 {
		return -((-v) / 2)
	}
	return v / 2
}

// BlitNativeTerrainCell composes one already-selected FDFIELD terrain cell as
// 0x11eee does: select the FDSHAP frame, then use raw 0x4deda only for entry
// byte+3 == 0xff, otherwise use LUT-aware 0x4dcc6. Camera iteration, LUT
// phase selection and foreground redraw remain responsibilities of its caller.
func (b *Bank) BlitNativeTerrainCell(dst []byte, stride, x, y, tile int, flags, blitMode byte, flip, cycle int, lut []byte) error {
	index, err := NativeTerrainFrameIndex(tile, flags, flip, cycle)
	if err != nil {
		return err
	}
	sprite, err := b.SpriteFor(index/12, (index%12)/3, index%3)
	if err != nil {
		return err
	}
	if blitMode == 0xff {
		return sprite.BlitAt(dst, stride, x, y)
	}
	return sprite.BlitLUT(dst, stride, x, y, lut)
}
