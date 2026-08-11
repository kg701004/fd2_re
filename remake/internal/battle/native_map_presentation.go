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

// NativeMapHUDRuntimeState is the raw persistent subset consumed by 0x1acf3.
// Display bytes retain byte identity; only their zero/nonzero tests are known.
type NativeMapHUDRuntimeState struct {
	DisplayGateA, DisplayGateB byte
	AnchorX                    int
}

// NativeMapHUDPersistentState separates the two values whose lifetimes cross
// battle nodes. DisplayGateA is also present in native chapter saves and the
// current-battle snapshot; AnchorX is process-local and is never serialized by
// the original. The provenance bits prevent a default Go zero from becoming a
// fabricated raw value.
type NativeMapHUDPersistentState struct {
	DisplayGateA    byte
	AnchorX         int
	HasDisplayGateA bool
	HasAnchorX      bool
}

// InitialNativeMapHUDPersistentState returns the two data-image seeds at
// [0x51AAB] and [0x51A0C]. Gate B is deliberately absent: it is a transient
// redraw gate with its own controller writers.
func InitialNativeMapHUDPersistentState() NativeMapHUDPersistentState {
	return NativeMapHUDPersistentState{
		DisplayGateA: 1, AnchorX: 1, HasDisplayGateA: true, HasAnchorX: true,
	}
}

// CaptureNativeMapHUD records only the two cross-node values from a complete
// runtime HUD state. It never carries the transient display gate B forward.
func (p *NativeMapHUDPersistentState) CaptureNativeMapHUD(runtime NativeMapHUDRuntimeState) bool {
	if p == nil {
		return false
	}
	contentWidth, contentHeight := defaultNativeMapHUDContentSize()
	if _, err := fdicon.NativeMapHUDLayoutFor(runtime.AnchorX, fdicon.NativeMapStride, contentWidth, contentHeight); err != nil {
		return false
	}
	p.DisplayGateA = runtime.DisplayGateA
	p.AnchorX = runtime.AnchorX
	p.HasDisplayGateA = true
	p.HasAnchorX = true
	return true
}

// RestoreSavedGateA applies the only HUD byte stored by both native save
// formats. AnchorX intentionally remains process-local.
func (p *NativeMapHUDPersistentState) RestoreSavedGateA(gateA byte) bool {
	if p == nil {
		return false
	}
	p.DisplayGateA = gateA
	p.HasDisplayGateA = true
	return true
}

// MaterializeRuntime combines the persistent pair with an explicitly sourced
// controller gate B. Missing provenance fails closed.
func (p NativeMapHUDPersistentState) MaterializeRuntime(gateB byte) (NativeMapHUDRuntimeState, bool) {
	if !p.HasDisplayGateA || !p.HasAnchorX {
		return NativeMapHUDRuntimeState{}, false
	}
	contentWidth, contentHeight := defaultNativeMapHUDContentSize()
	if _, err := fdicon.NativeMapHUDLayoutFor(p.AnchorX, fdicon.NativeMapStride, contentWidth, contentHeight); err != nil {
		return NativeMapHUDRuntimeState{}, false
	}
	return NativeMapHUDRuntimeState{
		DisplayGateA: p.DisplayGateA, DisplayGateB: gateB, AnchorX: p.AnchorX,
	}, true
}

func (s *State) MaterializeNativeMapHUDState(gateA, gateB byte, anchorX int) bool {
	if s == nil {
		return false
	}
	contentWidth, contentHeight := s.nativeMapHUDContentSize()
	if _, err := fdicon.NativeMapHUDLayoutFor(anchorX, fdicon.NativeMapStride, contentWidth, contentHeight); err != nil {
		return false
	}
	s.NativeMapHUDState = NativeMapHUDRuntimeState{
		DisplayGateA: gateA, DisplayGateB: gateB, AnchorX: anchorX,
	}
	s.HasNativeMapHUDState = true
	return true
}

// nativeMapHUDContentSize is the pixel content area the HUD panel is
// anchored within (312x192 -- 13x8 tiles -- at the original size), derived
// from the same active viewport as the steady map view (see
// nativeMapViewportOrDefault in native_map_view.go) so the two never drift.
func (s *State) nativeMapHUDContentSize() (contentWidth, contentHeight int) {
	cols, rows := s.nativeMapViewportOrDefault()
	return cols * fdicon.NativeSize, rows * fdicon.NativeSize
}

// defaultNativeMapHUDContentSize is nativeMapHUDContentSize's nil-State
// fallback, for the two persistent-state methods below that only see a value
// type and cannot reach the owning State's active viewport.
func defaultNativeMapHUDContentSize() (contentWidth, contentHeight int) {
	return nativeMapViewWidth * fdicon.NativeSize, nativeMapViewHeight * fdicon.NativeSize
}

// nativeMapHUDAnchorDodgeMargin is the fixed tile-count trigger zone on
// every edge of the HUD anchor deadzone (see AdvanceNativeMapHUDAnchor):
// reproduces the original's literal 3/9 thresholds at the 13-tile original
// width (3 and 13-1-3=9) and its dodge-away-from-cursor behavior for any
// wider remake viewport.
const nativeMapHUDAnchorDodgeMargin = 3

// AdvanceNativeMapHUDAnchor applies the only two proven writes in 0x1acf3.
// rawVisibleX/Y are [0x53ab9]/[0x53abd], not dialogue-box dimensions. The
// panel dodges to the flush-right anchor when the cursor nears the left
// edge, to flush-left when it nears the right edge, and only within the
// bottom two viewport rows (matching indexedmap.AdvanceNativeMapHUDAnchor's
// row deadzone) -- see nativeMapHUDContentSize for how this generalizes to
// a wider/taller remake viewport instead of the original fixed 13x8.
func (s *State) AdvanceNativeMapHUDAnchor(rawVisibleX, rawVisibleY int) bool {
	if s == nil || !s.HasNativeMapHUDState {
		return false
	}
	viewCols, viewRows := s.nativeMapViewportOrDefault()
	contentWidth, contentHeight := s.nativeMapHUDContentSize()
	next := s.NativeMapHUDState.AnchorX
	if rawVisibleY > viewRows-1-2 {
		if rawVisibleX < nativeMapHUDAnchorDodgeMargin {
			next = contentWidth - fdicon.NativeMapHUDPanelWidth - 1
		} else if rawVisibleX > viewCols-1-nativeMapHUDAnchorDodgeMargin {
			next = 1
		}
	}
	if _, err := fdicon.NativeMapHUDLayoutFor(next, fdicon.NativeMapStride, contentWidth, contentHeight); err != nil {
		return false
	}
	s.NativeMapHUDState.AnchorX = next
	return true
}

// NativeMapFrameRoster is the atomically materialized roster subset consumed
// by the steady unit and foreground layers. Cycles are the battle-session
// globals selected by those same entries.
type NativeMapFrameRoster struct {
	Units          []fdicon.NativeUnitLayerEntry
	Foreground     []fdicon.NativeForegroundLayerEntry
	Cycles         fdicon.NativeMapSpriteCycleState
	TerrainPhase   int
	TerrainFlip    int
	UnitPixelShift int
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

// SetNativeMapCoordinatesRaw mirrors a direct write to runtime bytes +0/+1.
// Unlike SetMapPlacement it deliberately preserves +3 pose and +4 motion:
// hard-coded handlers may update only the two coordinate bytes, and clearing
// adjacent presentation state would invent a write that is absent in the EXE.
func (u *Unit) SetNativeMapCoordinatesRaw(x, y int) bool {
	if u == nil || !u.HasNativeMapPresentation || x < 0 || x > 0xff || y < 0 || y > 0xff {
		return false
	}
	u.X, u.Y = x, y
	u.NativeMapPresentation.X = byte(x)
	u.NativeMapPresentation.Y = byte(y)
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

// NativeForegroundLayerEntry returns the exact raw subset consumed by
// 0x129ec. BattleFig's legacy Fig fallback is rejected: unit+7, race and class
// must each carry explicit native provenance.
func (u *Unit) NativeForegroundLayerEntry() (fdicon.NativeForegroundLayerEntry, bool) {
	if u == nil || !u.HasNativeMapPresentation || !u.HasNativeRecordByte5 ||
		!u.HasBattleFig || u.BattleFig < 0 || u.BattleFig > 0xff ||
		!u.HasNativeRecordRace || !u.HasNativeRecordClass {
		return fdicon.NativeForegroundLayerEntry{}, false
	}
	raw := u.NativeMapPresentation
	return fdicon.NativeForegroundLayerEntry{
		X: int(raw.X), Y: int(raw.Y), Pose: raw.Pose,
		MotionOffset: int(raw.Motion), Inactive: u.NativeRecordByte5&1 != 0,
		Unit7: byte(u.BattleFig), Race: u.NativeRecordRace, Class: u.NativeRecordClass,
	}, true
}

// NativeMapFrameRoster materializes one complete compositor input snapshot.
// The native loop has no nil or guessed records, so any missing provenance
// rejects the entire roster instead of producing a partially native frame.
func (s *State) NativeMapFrameRoster() (NativeMapFrameRoster, error) {
	if s == nil || s.NativeMapSelectorError != nil || s.NativeMapSelectorCache == nil ||
		!s.HasNativeMapCycleState || !s.HasNativeTerrainPhaseState ||
		!s.HasNativeMapBinaryTimingState {
		return NativeMapFrameRoster{}, fmt.Errorf("battle: native map frame state is incomplete")
	}
	out := NativeMapFrameRoster{
		Units:          make([]fdicon.NativeUnitLayerEntry, len(s.Units)),
		Foreground:     make([]fdicon.NativeForegroundLayerEntry, len(s.Units)),
		Cycles:         s.NativeMapCycleState,
		TerrainPhase:   s.NativeTerrainPhaseState.Phase,
		TerrainFlip:    s.NativeTerrainFlipState.Value,
		UnitPixelShift: s.NativeUnitPixelShiftState.Value,
	}
	for i, u := range s.Units {
		unit, ok := u.NativeUnitLayerEntry()
		if !ok {
			return NativeMapFrameRoster{}, fmt.Errorf("battle: native map frame unit %d lacks unit-layer provenance", i)
		}
		foreground, ok := u.NativeForegroundLayerEntry()
		if !ok {
			return NativeMapFrameRoster{}, fmt.Errorf("battle: native map frame unit %d lacks foreground provenance", i)
		}
		out.Units[i], out.Foreground[i] = unit, foreground
	}
	return out, nil
}
