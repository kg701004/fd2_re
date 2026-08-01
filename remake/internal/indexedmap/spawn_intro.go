package indexedmap

import (
	"errors"
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

// NativeSpawnIntroFrameInput binds the complete post-constructor roster to
// the old/new slot boundary saved by 0x32999 before its 0x10B4E call.
type NativeSpawnIntroFrameInput struct {
	Frame        NativeTransitionFrameInput
	OldUnitCount int
}

func validateNativeSpawnIntroFrameInput(in NativeSpawnIntroFrameInput) error {
	f := in.Frame
	if in.OldUnitCount < 0 || in.OldUnitCount > len(f.Units) ||
		len(f.Units) != len(f.ForegroundUnits) || f.UnitBank == nil ||
		f.ForegroundBank == nil || f.SelectorCache == nil {
		return errors.New("indexedmap: incomplete native spawn-intro roster boundary")
	}
	return nil
}

func redrawNativeSpawnIntroSplit(
	dst []byte,
	in NativeSpawnIntroFrameInput,
	newUnitPixelLift int,
) error {
	if len(dst) != NativeUnitPresentWorkSize || newUnitPixelLift > 0 {
		return errors.New("indexedmap: invalid native spawn-intro split target")
	}
	f := in.Frame
	frame := append([]byte(nil), dst...)
	if err := f.UnitBank.BlitNativeUnitLayer(
		frame, workStride, f.SelectorCache, f.Units[:in.OldUnitCount],
		f.CameraX, f.CameraY, 12, 7,
		f.IdleCycle, f.MovingCycle, f.PixelShift,
	); err != nil {
		return fmt.Errorf("indexedmap: spawn-intro old units: %w", err)
	}
	if err := f.UnitBank.BlitNativeUnitLayerWithBaseShift(
		frame, workStride, f.SelectorCache, f.Units[in.OldUnitCount:],
		f.CameraX, f.CameraY, 12, 7,
		f.IdleCycle, f.MovingCycle, f.PixelShift,
		newUnitPixelLift*workStride,
	); err != nil {
		return fmt.Errorf("indexedmap: spawn-intro new units: %w", err)
	}
	if err := f.ForegroundBank.BlitNativeForegroundLayer(
		frame, workStride, f.ForegroundUnits,
		f.MapWidth, f.Cells, f.Controls,
		f.CameraX, f.CameraY, 12, 7,
		f.Flip, f.TerrainLUT,
	); err != nil {
		return fmt.Errorf("indexedmap: spawn-intro foreground: %w", err)
	}
	copy(dst, frame)
	return nil
}

// ComposeNativeSpawnIntroPass executes one complete 0x32999 iteration. The
// visible VGA frame is captured before pass 6/7/8 rebuild the private snapshot,
// matching the original call order. All three caller buffers remain unchanged
// if any asset, roster selector, geometry, or layer operation fails.
func ComposeNativeSpawnIntroPass(
	work, vga, snapshot []byte,
	in NativeSpawnIntroFrameInput,
	entry fdother.LMI1Entry,
	step fdother.NativeSpawnIntroStep,
) error {
	if len(work) != NativeUnitPresentWorkSize || len(snapshot) != NativeUnitPresentWorkSize ||
		len(vga) < NativeMapVGASize {
		return errors.New("indexedmap: incomplete native spawn-intro buffers")
	}
	if err := validateNativeSpawnIntroFrameInput(in); err != nil {
		return err
	}
	schedule := fdother.NativeSpawnIntroSchedule()
	if step.Pass < 0 || step.Pass >= len(schedule) || step != schedule[step.Pass] {
		return errors.New("indexedmap: native spawn-intro step differs from 0x32999")
	}

	frame := append([]byte(nil), snapshot...)
	f := in.Frame
	for _, unit := range f.Units[in.OldUnitCount:] {
		if !fdother.NativeSpawnIntroVisible(unit.X, unit.Y, f.CameraX, f.CameraY, 12, 7) {
			continue
		}
		if err := fdother.BlitNativeSpawnIntroLMI(entry, frame, unit.X, unit.Y, f.CameraX, f.CameraY); err != nil {
			return fmt.Errorf("indexedmap: spawn-intro pass %d LMI: %w", step.Pass, err)
		}
	}
	viewport := append([]byte(nil), vga...)
	if err := CopyNativeUnitPresentViewport(viewport, frame); err != nil {
		return fmt.Errorf("indexedmap: spawn-intro pass %d present: %w", step.Pass, err)
	}

	nextSnapshot := append([]byte(nil), snapshot...)
	switch step.SnapshotMode {
	case fdother.NativeSpawnIntroKeepSnapshot:
		// The next pass restores the unchanged pre-existing snapshot.
	case fdother.NativeSpawnIntroSplitUnits:
		if step.RedrawTerrain {
			if err := ComposeNativeUnitPresentTerrainSnapshot(nextSnapshot, f); err != nil {
				return fmt.Errorf("indexedmap: spawn-intro pass %d terrain: %w", step.Pass, err)
			}
		}
		if err := redrawNativeSpawnIntroSplit(nextSnapshot, in, step.NewUnitPixelLift); err != nil {
			return fmt.Errorf("indexedmap: spawn-intro pass %d split: %w", step.Pass, err)
		}
	case fdother.NativeSpawnIntroFullFrame:
		if !step.RedrawTerrain || step.NewUnitPixelLift != 0 {
			return errors.New("indexedmap: invalid full spawn-intro snapshot step")
		}
		if err := ComposeNativeUnitPresentTerrainSnapshot(nextSnapshot, f); err != nil {
			return fmt.Errorf("indexedmap: spawn-intro pass %d terrain: %w", step.Pass, err)
		}
		if err := RedrawNativeUnitPresentObjects(nextSnapshot, f); err != nil {
			return fmt.Errorf("indexedmap: spawn-intro pass %d objects: %w", step.Pass, err)
		}
	default:
		return errors.New("indexedmap: unknown native spawn-intro snapshot mode")
	}

	copy(vga, viewport)
	if step.SnapshotMode == fdother.NativeSpawnIntroKeepSnapshot {
		copy(work, frame)
	} else {
		copy(snapshot, nextSnapshot)
		copy(work, nextSnapshot)
	}
	return nil
}

// SeedNativeSpawnIntroSnapshot captures the exact pre-constructor work buffer.
// It is deliberately a full 0x25680-byte copy, not a cropped visible frame.
func SeedNativeSpawnIntroSnapshot(work []byte) ([]byte, error) {
	if len(work) != NativeUnitPresentWorkSize {
		return nil, errors.New("indexedmap: native spawn-intro seed must be exactly 0x25680 bytes")
	}
	return append([]byte(nil), work...), nil
}
