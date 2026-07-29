package campaign

import (
	"encoding/binary"
	"reflect"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdsave"
)

func continueFieldBoundaryInput(t *testing.T) fdsave.ContinueRuntimeInput {
	t.Helper()
	snapshot := fdsave.CurrentSnapshot{
		Header: fdsave.CurrentRuntimeHeader{
			TurnCounter: 7, RuntimeCount: 1, Chapter: 1,
			CameraX: 1, CameraY: 2,
			CursorX: 8, CursorY: 7,
			VisibleCursorX: 7, VisibleCursorY: 5,
			PersistentCount: 1, HUDGateA: 0xa1,
		},
		RuntimeRecords: make([]fdsave.PersistentRecord, 1),
	}
	snapshot.RuntimeRecords[0].Raw[0] = 8
	snapshot.RuntimeRecords[0].Raw[1] = 7
	snapshot.RuntimeRecords[0].Raw[7] = 5
	snapshot.NativeFieldControl[2] = 1
	copy(snapshot.NativeFieldControl[3:6], []byte{9, 10, 11})
	copy(snapshot.NativeFieldControl[0x33:0x35], []byte{12, 13})
	snapshot.NativeFieldControl[0x53] = 14
	binary.LittleEndian.PutUint16(snapshot.NativeFieldControl[0x54:0x56], 0x1234)
	snapshot.NativeFieldControl[fdsave.CurrentFieldControlUnitOffset] = 15
	snapshot.NativeEventState[12] = 16

	input, err := fdsave.BuildContinueRuntimeInput(
		snapshot,
		fdsave.ContinueRuntimeContext{
			Chapter: 1, FieldWidth: 30, FieldHeight: 20,
			SelectorGroupCount: 16,
			TitleTimerTick:     -123, HasTitleTimerTick: true,
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	return input
}

func continueFieldBoundaryState() *battle.State {
	return &battle.State{
		W: 30, H: 20,
		NativeFieldEventSlots: make([]int, 30*20),
		NativeFieldEvents:     make([]battle.NativeFieldEvent, 16),
		Units:                 []*battle.Unit{{Name: "sentinel"}},
	}
}

func TestMaterializeNativeContinueFieldBoundaryInstallsLiveStateAtomically(t *testing.T) {
	input := continueFieldBoundaryInput(t)
	state := continueFieldBoundaryState()
	if err := MaterializeNativeContinueFieldBoundary(state, input, 1); err != nil {
		t.Fatal(err)
	}
	if !state.HasNativeFieldControlState ||
		state.NativeRoundCounter != 7 ||
		state.NativeEventState[12] != 16 ||
		state.NativeTurnEventControls[0] != (battle.NativeTurnEventControl{
			Turn: 9, EventID: 10, RawCamp: 11,
		}) ||
		state.NativeFieldEvents[0] != (battle.NativeFieldEvent{
			EventID: 12, Selector: 13,
		}) ||
		state.NativeChestControls[0] != (battle.NativeChestControl{
			RawType: 14, Value: 0x1234,
		}) ||
		len(state.NativeFieldUnitControls) != 1 ||
		state.NativeFieldUnitControls[0].Raw[0] != 15 ||
		len(state.NativeRuntimeRecords) != 1 ||
		state.NativeRuntimeRecords[0].Raw[7] != 5 ||
		state.NativeRuntimeRecords[0].SelectorKey != 5 ||
		state.NativeRuntimeRecords[0].SelectorSlot != 0 {
		t.Fatalf("materialized field boundary=%#v", state)
	}
	if !state.HasNativeMapViewState || !state.HasNativeMapHUDState ||
		!state.HasNativeMapRangeModeState || state.NativeMapRangeMode != 0 ||
		len(state.Units) != 1 || state.Units[0].Name != "sentinel" {
		t.Fatalf("materialized view/roster boundary=%#v", state)
	}
	if state.HasNativeMapCycleState || state.HasNativeTerrainPhaseState ||
		state.HasNativeMapBinaryTimingState {
		t.Fatal("field boundary guessed unresolved timing state")
	}

	input.NativeFieldControl[0] ^= 0xff
	input.FieldControl.Units[0].Raw[0] ^= 0xff
	input.RuntimeRecords[0].Raw.Raw[7] ^= 0xff
	if state.NativeFieldControlRaw[0] == input.NativeFieldControl[0] ||
		state.NativeFieldUnitControls[0].Raw[0] == input.FieldControl.Units[0].Raw[0] ||
		state.NativeRuntimeRecords[0].Raw[7] == input.RuntimeRecords[0].Raw.Raw[7] {
		t.Fatal("field boundary aliases CONTINUE input")
	}
}

func TestMaterializeNativeContinueFieldBoundaryRejectsBeforeMutation(t *testing.T) {
	input := continueFieldBoundaryInput(t)
	tests := map[string]func(*battle.State, *fdsave.ContinueRuntimeInput) int{
		"unvalidated input": func(_ *battle.State, input *fdsave.ContinueRuntimeInput) int {
			*input = fdsave.ContinueRuntimeInput{}
			return 1
		},
		"tampered validated input": func(_ *battle.State, input *fdsave.ContinueRuntimeInput) int {
			input.NativeFieldControl[3]++
			return 1
		},
		"chapter mismatch": func(_ *battle.State, _ *fdsave.ContinueRuntimeInput) int {
			return 2
		},
		"dimension mismatch": func(state *battle.State, _ *fdsave.ContinueRuntimeInput) int {
			state.W++
			return 1
		},
		"missing field events": func(state *battle.State, _ *fdsave.ContinueRuntimeInput) int {
			state.NativeFieldEvents = nil
			return 1
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			state := continueFieldBoundaryState()
			candidate := input
			assetChapter := mutate(state, &candidate)
			before := *state
			beforeSlots := append([]int(nil), state.NativeFieldEventSlots...)
			beforeEvents := append([]battle.NativeFieldEvent(nil), state.NativeFieldEvents...)
			if err := MaterializeNativeContinueFieldBoundary(
				state, candidate, assetChapter,
			); err == nil {
				t.Fatal("malformed field boundary was accepted")
			}
			if !reflect.DeepEqual(state.Units, before.Units) ||
				!reflect.DeepEqual(state.NativeFieldEventSlots, beforeSlots) ||
				!reflect.DeepEqual(state.NativeFieldEvents, beforeEvents) ||
				state.HasNativeFieldControlState {
				t.Fatalf("rejected field boundary mutated state=%#v", state)
			}
		})
	}
}
