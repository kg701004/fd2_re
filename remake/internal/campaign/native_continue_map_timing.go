package campaign

import (
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdsave"
)

// MaterializeNativeContinueMapTiming installs the exact process-global seed
// observed immediately before sub_10010's first 0x11CAC redraw. It does not
// sample a clock or schedule either redraw; those are caller-owned operations.
//
// Field and runtime-unit adapters must already have succeeded. This preserves
// the original order and prevents a timing-only partial CONTINUE state.
func MaterializeNativeContinueMapTiming(
	state *battle.State,
	input fdsave.ContinueRuntimeInput,
) error {
	if state == nil {
		return fmt.Errorf("native CONTINUE map timing: nil battle state")
	}
	if !input.ValidatedForRuntimeBridge() {
		return fmt.Errorf("native CONTINUE map timing: input did not pass preflight")
	}
	if !state.HasNativeFieldControlState ||
		!state.HasNativeRuntimeUnitProjection ||
		!state.HasNativeMapViewState ||
		!state.HasNativeMapRangeModeState ||
		state.NativeMapRangeMode != input.MapPresentation.OpeningRangeMode {
		return fmt.Errorf("native CONTINUE map timing: prior runtime boundary is incomplete")
	}

	seed := input.MapTimingSeed
	if seed.SpriteIdleCycle < 0 || seed.SpriteIdleCycle > 3 ||
		seed.SpriteMovingCycle < 0 || seed.SpriteMovingCycle > 3 ||
		seed.SpriteLastTimerTick < -0x8000 || seed.SpriteLastTimerTick > 0x7fff ||
		seed.TerrainPhase < 0 || seed.TerrainPhase >= 20 ||
		seed.TerrainPhaseLastTimerTick < -0x8000 || seed.TerrainPhaseLastTimerTick > 0x7fff ||
		seed.TerrainPhaseOverride != -1 ||
		(seed.TerrainFlip != 0 && seed.TerrainFlip != 1) ||
		seed.TerrainFlipLastTimerTick < -0x8000 || seed.TerrainFlipLastTimerTick > 0x7fff ||
		(seed.UnitPixelShift != 0 && seed.UnitPixelShift != 1) ||
		seed.UnitPixelShiftLastTimerTick < -0x8000 || seed.UnitPixelShiftLastTimerTick > 0x7fff {
		return fmt.Errorf("native CONTINUE map timing: seed is outside raw bounds")
	}

	candidate := *state
	candidate.NativeMapCycleState = fdicon.NativeMapSpriteCycleState{
		Idle:          seed.SpriteIdleCycle,
		Moving:        seed.SpriteMovingCycle,
		LastTimerTick: seed.SpriteLastTimerTick,
	}
	candidate.NativeTerrainPhaseState = fdother.NativeTerrainPhaseState{
		Phase:         seed.TerrainPhase,
		LastTimerTick: seed.TerrainPhaseLastTimerTick,
	}
	candidate.NativeTerrainFlipState = fdicon.NativeBinaryTickState{
		Value:         seed.TerrainFlip,
		LastTimerTick: seed.TerrainFlipLastTimerTick,
	}
	candidate.NativeUnitPixelShiftState = fdicon.NativeBinaryTickState{
		Value:         seed.UnitPixelShift,
		LastTimerTick: seed.UnitPixelShiftLastTimerTick,
	}
	candidate.HasNativeMapCycleState = true
	candidate.HasNativeTerrainPhaseState = true
	candidate.HasNativeMapBinaryTimingState = true
	*state = candidate
	return nil
}
