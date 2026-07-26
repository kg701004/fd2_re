package fdicon

import "errors"

// NativeUnitLayerEntry is the raw subset consumed by 0x127a9/0x127e0.  Slot
// is runtime unit+2 (not a sprite group); Pose, MotionOffset and ForceBase are
// unit+3, +4 and +0x26 respectively.  Inactive represents the preceding
// 0x3453e roster gate.
type NativeUnitLayerEntry struct {
	X, Y         int
	Slot         int
	Pose         int
	MotionOffset int
	Flags        byte
	ForceBase    bool
	Inactive     bool
}

type nativeUnitBlit struct {
	sprite Sprite
	offset int
	flags  byte
}

// BlitNativeUnitLayer reproduces the steady 0x127a9 roster pass.  The caller
// supplies the raw visible extents read by 0x127e0, rather than this adapter
// assigning semantic camera dimensions: native accepts X in [cameraX-1,
// cameraX+visibleXMax] and Y in [cameraY-1, cameraY+visibleYMax+1].  It
// preflights every selected entry before modifying dst, so malformed editable
// selector state cannot produce a partial indexed frame.
func (b *Bank) BlitNativeUnitLayer(dst []byte, stride int, cache *NativeSelectorCache, units []NativeUnitLayerEntry, cameraX, cameraY, visibleXMax, visibleYMax, idleCycle, movingCycle, pixelShift int) error {
	if b == nil || cache == nil || stride != NativeMapStride || visibleXMax < 0 || visibleYMax < 0 {
		return errors.New("fdicon: invalid native unit layer")
	}
	commands := make([]nativeUnitBlit, 0, len(units))
	for _, unit := range units {
		if unit.Inactive {
			continue
		}
		if unit.X < cameraX-1 || unit.X > cameraX+visibleXMax || unit.Y < cameraY-1 || unit.Y > cameraY+visibleYMax+1 {
			continue
		}
		cycle, err := NativeFrameIndex(unit.MotionOffset, unit.ForceBase, idleCycle, movingCycle)
		if err != nil {
			return err
		}
		sprite, err := b.SpriteForNativeSlot(cache, unit.Slot, unit.Pose, cycle)
		if err != nil {
			return err
		}
		offset, err := NativePlacementOffset(unit.X, unit.Y, cameraX, cameraY, unit.Pose, unit.MotionOffset, pixelShift, unit.ForceBase)
		if err != nil {
			return err
		}
		if offset < 0 { // 0x127e0 skips a negative native pointer offset.
			continue
		}
		if offset+(NativeSize-1)*stride+NativeSize > len(dst) {
			return errors.New("fdicon: native unit layer exceeds destination")
		}
		commands = append(commands, nativeUnitBlit{sprite: sprite, offset: offset, flags: unit.Flags})
	}
	for _, command := range commands {
		if err := command.sprite.BlitForNativeFlagsAtOffset(dst, stride, command.offset, command.flags); err != nil {
			return err
		}
	}
	return nil
}
