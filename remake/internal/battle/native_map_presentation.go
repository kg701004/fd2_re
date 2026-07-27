package battle

import (
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
)

// NativeMapPresentationState is the battle-local runtime record subset used
// by 0x127e0. It is intentionally independent of normalized X/Y/Dir/OffX/OffY:
// native grid movement keeps X/Y on the source cell while Motion advances
// 1..6, then commits the destination and clears Motion at tick seven.
type NativeMapPresentationState struct {
	X, Y   byte
	Pose   byte
	Motion byte
}

// MaterializeNativeMapPresentation reproduces the constructor's initial
// +0/+1 coordinates and +3/+4=0/0. Callers must establish the native selector
// slot separately; this method performs no identity/Fig fallback.
func (u *Unit) MaterializeNativeMapPresentation() error {
	if u == nil || u.X < 0 || u.X > 0xff || u.Y < 0 || u.Y > 0xff {
		return fmt.Errorf("battle: native map presentation coordinate outside byte range")
	}
	u.NativeMapPresentation = NativeMapPresentationState{X: byte(u.X), Y: byte(u.Y)}
	u.HasNativeMapPresentation = true
	u.Dir = 0
	u.OffX, u.OffY = 0, 0
	return nil
}

// SetMapPose updates the normalized direction and, when materialized, raw
// unit+3. It never fabricates native provenance for a legacy unit.
func (u *Unit) SetMapPose(pose int) bool {
	if u == nil || pose < 0 || pose > 3 {
		return false
	}
	u.Dir = pose
	if u.HasNativeMapPresentation {
		u.NativeMapPresentation.Pose = byte(pose)
	}
	return true
}

// SetMapPlacement updates an out-of-motion placement writer. Materialized
// native state receives the same byte coordinates and a zero motion offset;
// legacy units retain only the normalized projection.
func (u *Unit) SetMapPlacement(x, y, pose int) bool {
	if u == nil || x < 0 || x > 0xff || y < 0 || y > 0xff || pose < 0 || pose > 3 {
		return false
	}
	u.X, u.Y, u.Dir = x, y, pose
	u.OffX, u.OffY = 0, 0
	if u.HasNativeMapPresentation {
		u.NativeMapPresentation = NativeMapPresentationState{
			X: byte(x), Y: byte(y), Pose: byte(pose),
		}
	}
	return true
}

// SetNativeMapGridMotion writes one native in-cell step. X/Y deliberately
// remain on the source cell. motion is the exact unit+4 range 1..6.
func (u *Unit) SetNativeMapGridMotion(pose, motion int) bool {
	if u == nil || !u.HasNativeMapPresentation || pose < 0 || pose > 3 || motion < 1 || motion > 6 {
		return false
	}
	u.Dir = pose
	u.NativeMapPresentation.Pose = byte(pose)
	u.NativeMapPresentation.Motion = byte(motion)
	return true
}

// FinishNativeMapGridStep reproduces the seventh-tick commit: destination
// bytes replace +0/+1, +4 becomes zero, and +3 retains the movement pose.
func (u *Unit) FinishNativeMapGridStep(pose, x, y int) bool {
	if u == nil || !u.HasNativeMapPresentation ||
		pose < 0 || pose > 3 || x < 0 || x > 0xff || y < 0 || y > 0xff {
		return false
	}
	u.X, u.Y, u.Dir = x, y, pose
	u.OffX, u.OffY = 0, 0
	u.NativeMapPresentation = NativeMapPresentationState{
		X: byte(x), Y: byte(y), Pose: byte(pose), Motion: 0,
	}
	return true
}

// NativeUnitLayerEntry returns the exact raw subset required by 0x127e0 and
// its preceding inactive gate. Missing selector/record/presentation
// provenance fails closed rather than projecting normalized fields.
func (u *Unit) NativeUnitLayerEntry() (fdicon.NativeUnitLayerEntry, bool) {
	if u == nil || !u.HasNativeMapPresentation || !u.HasMapSelectorSlot || !u.HasNativeRecordByte5 {
		return fdicon.NativeUnitLayerEntry{}, false
	}
	raw := u.NativeMapPresentation
	return fdicon.NativeUnitLayerEntry{
		X: int(raw.X), Y: int(raw.Y),
		Slot: u.MapSelectorSlot, Pose: int(raw.Pose), MotionOffset: int(raw.Motion),
		Flags: u.NativeRecordByte5, ForceBase: u.NativeTransient[4] != 0,
		Inactive: u.NativeRecordByte5&1 != 0,
	}, true
}
