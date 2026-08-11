package fdicon

import "errors"

// NativeForegroundLayerEntry is the raw unit subset used by 0x129ec.  Unit7,
// Race and Class are passed through without assigning gameplay names because
// they feed the separately recovered 0x1f183 eligibility gate.
type NativeForegroundLayerEntry struct {
	X, Y               int
	Pose               byte
	MotionOffset       int
	Inactive           bool
	Unit7, Race, Class byte
}

type nativeForegroundBlit struct {
	sprite Sprite
	offset int
	raw    bool
}

// nativeForegroundLayerWorkBase reproduces the original 0x8088 native
// placement origin for the recovered {stride:456} case. See
// nativeUnitLayerWorkBase in unit_layer.go for the same pattern.
const nativeForegroundLayerWorkBase = 0x8088

// BlitNativeForegroundLayer composes the steady 0x129ec→0x12ac6 foreground
// pass after units.  Its camera tests are the recovered callee ABI.  Unlike
// native unchecked memory, an off-map scheduled coordinate is skipped before
// indexing cells; this is an explicit fail-closed safety boundary, not a claim
// about original out-of-range memory contents.  As with the unit layer, all
// valid selected blits are preflighted before dst changes. It always uses the
// original recovered work-buffer origin (0x8088); callers at a wider
// viewport must use BlitNativeForegroundLayerAt instead.
func (b *Bank) BlitNativeForegroundLayer(dst []byte, stride int, units []NativeForegroundLayerEntry, mapWidth int, cells []NativeTerrainCell, controls []byte, cameraX, cameraY, visibleXMax, visibleYMax, flip int, lut []byte) error {
	return b.BlitNativeForegroundLayerAt(dst, nativeForegroundLayerWorkBase, stride, units, mapWidth, cells, controls, cameraX, cameraY, visibleXMax, visibleYMax, flip, lut)
}

// BlitNativeForegroundLayerAt is BlitNativeForegroundLayer generalized to an
// explicit work-buffer origin, for viewports wider than the original 13x8
// (see indexedmap.NativeMapViewport). stride below NativeMapStride is
// rejected as a minimum-bound guard, not the original exact-match gate.
func (b *Bank) BlitNativeForegroundLayerAt(dst []byte, workBase, stride int, units []NativeForegroundLayerEntry, mapWidth int, cells []NativeTerrainCell, controls []byte, cameraX, cameraY, visibleXMax, visibleYMax, flip int, lut []byte) error {
	if b == nil || stride < NativeMapStride || mapWidth <= 0 || len(cells)%mapWidth != 0 || visibleXMax < 0 || visibleYMax < 0 || (flip != 0 && flip != 1) {
		return errors.New("fdicon: invalid native foreground layer")
	}
	mapHeight := len(cells) / mapWidth
	commands := make([]nativeForegroundBlit, 0)
	for _, unit := range units {
		if !NativeForegroundRedrawEligible(unit.Inactive, unit.Unit7, unit.Race, unit.Class) {
			continue
		}
		coords, count := NativeForegroundRedrawCells(unit.X, unit.Y, unit.Pose, unit.MotionOffset)
		for _, coord := range coords[:count] {
			if coord.X < cameraX-1 || coord.X > cameraX+visibleXMax || coord.Y < cameraY-1 || coord.Y > cameraY+visibleYMax+1 || coord.Y < 0 || coord.X < 0 || coord.X >= mapWidth || coord.Y >= mapHeight {
				continue
			}
			cell := cells[coord.Y*mapWidth+coord.X]
			tile := int(cell.Tile & 0x3ff)
			if tile*4 >= len(controls) {
				return errors.New("fdicon: foreground terrain control table is too short")
			}
			index, present, err := NativeForegroundFrameIndex(tile, controls[tile*4], flip)
			if err != nil || !present {
				if err != nil {
					return err
				}
				continue
			}
			sprite, err := b.SpriteFor(index/12, (index%12)/3, index%3)
			if err != nil {
				return err
			}
			if cell.BlitMode != 0xff && len(lut) != 256 {
				return errors.New("fdicon: foreground LUT is invalid")
			}
			offset := workBase + (coord.Y-cameraY)*NativeSize*stride + (coord.X-cameraX)*NativeSize
			if offset < 0 || offset+(NativeSize-1)*stride+NativeSize > len(dst) {
				return errors.New("fdicon: native foreground layer exceeds destination")
			}
			commands = append(commands, nativeForegroundBlit{sprite: sprite, offset: offset, raw: cell.BlitMode == 0xff})
		}
	}
	for _, command := range commands {
		if command.raw {
			if err := command.sprite.BlitForNativeFlagsAtOffset(dst, stride, command.offset, 0); err != nil {
				return err
			}
		} else if err := command.sprite.BlitLUTTransparentAtOffset(dst, stride, command.offset, lut); err != nil {
			return err
		}
	}
	return nil
}
