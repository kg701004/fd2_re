package campaign

import (
	"encoding/binary"
	"os"
	"reflect"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdsave"
)

func TestMaterializeNativeContinueRuntimeUnitsOriginalSnapshot(t *testing.T) {
	path := os.Getenv("FD2_NATIVE_SAVE_FIXTURE")
	if path == "" {
		t.Skip("set FD2_NATIVE_SAVE_FIXTURE to a user-provided original FD2.SAV")
	}
	stored, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	plain, err := fdsave.Decode(stored)
	if err != nil {
		t.Fatal(err)
	}
	snapshot, err := fdsave.InspectCurrentSnapshot(plain)
	if err != nil {
		t.Fatal(err)
	}
	input, err := fdsave.BuildContinueRuntimeInput(
		snapshot,
		fdsave.ContinueRuntimeContext{
			Chapter: int(snapshot.Header.Chapter),
			// The supplied reference snapshot is chapter 0, whose original
			// field is 31×24. Resource identity remains explicit here.
			FieldWidth: 31, FieldHeight: 24,
			SelectorGroupCount: 256,
			TitleTimerTick:     0, HasTitleTimerTick: true,
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	state := &battle.State{
		W: 31, H: 24,
		NativeFieldEventSlots: make([]int, 31*24),
		NativeFieldEvents:     make([]battle.NativeFieldEvent, 16),
	}
	if err := MaterializeNativeContinueFieldBoundary(
		state, input, int(snapshot.Header.Chapter),
	); err != nil {
		t.Fatal(err)
	}
	if err := MaterializeNativeContinueRuntimeUnits(
		state, input, nativeRuntimeCatalog(t),
	); err != nil {
		t.Fatal(err)
	}
	if len(state.Units) != 12 {
		t.Fatalf("runtime units=%d, want 12", len(state.Units))
	}
	gotNames := []string{
		state.Units[0].Name,
		state.Units[1].Name,
		state.Units[2].Name,
		state.Units[3].Name,
	}
	if want := []string{"索爾", "悠妮", "亞雷斯", "蓋亞"}; !reflect.DeepEqual(gotNames, want) {
		t.Fatalf("own runtime names=%v, want %v", gotNames, want)
	}
	if state.Units[4].Camp != battle.Enemy ||
		state.Units[4].HasNativeIdentity ||
		state.Units[4].NativeRecordByte8 != 96 {
		t.Fatalf("enemy runtime +8 was misclassified: %#v", state.Units[4])
	}
}

func continueRuntimeUnitsInput(
	t *testing.T,
	mutate func([]fdsave.PersistentRecord),
) fdsave.ContinueRuntimeInput {
	t.Helper()
	records := make([]fdsave.PersistentRecord, 3)
	for index := range records {
		record := &records[index].Raw
		record[0], record[1] = byte(4+index), byte(5+index)
		record[3], record[4] = byte(index), byte(index+1)
		record[5], record[6] = 0, 0
		record[7], record[8] = 0x60, 0x60
		for slot := 0; slot < 8; slot++ {
			record[0x0a+slot*2] = 0x80
			record[0x0b+slot*2] = 0xff
		}
		record[0x1f], record[0x20], record[0x21] = 1, 7, 2
		record[0x3b], record[0x3c] = 5, 9
		for offset, value := range map[int]int16{
			0x37: 10, 0x39: 11, 0x3e: 12,
			0x40: 13, 0x42: 14, 0x44: 15, 0x46: 16,
			0x48: 17, 0x4a: 18, 0x4c: 19, 0x4e: 20,
		} {
			binary.LittleEndian.PutUint16(record[offset:], uint16(value))
		}
	}
	records[0].Raw[6], records[0].Raw[7], records[0].Raw[8] = 2, 9, 9
	records[0].Raw[2] = 0xee
	records[0].Raw[0x0a], records[0].Raw[0x0b] = 0x40, 0x12
	copy(records[0].Raw[0x22:0x28], []byte{1, 2, 3, 4, 5, 6})
	records[1].Raw[5] = 1
	records[1].Raw[0], records[1].Raw[1] = 0xff, 0xfe
	records[1].Raw[3], records[1].Raw[4] = 0xfd, 0xfc
	records[1].Raw[2] = 0xed
	records[2].Raw[2] = 0xec
	if mutate != nil {
		mutate(records)
	}

	snapshot := fdsave.CurrentSnapshot{
		Header: fdsave.CurrentRuntimeHeader{
			TurnCounter: 7, RuntimeCount: byte(len(records)), Chapter: 1,
			CameraX: 1, CameraY: 2,
			CursorX: 8, CursorY: 7,
			VisibleCursorX: 7, VisibleCursorY: 5,
		},
		RuntimeRecords: records,
	}
	input, err := fdsave.BuildContinueRuntimeInput(
		snapshot,
		fdsave.ContinueRuntimeContext{
			Chapter: 1, FieldWidth: 30, FieldHeight: 20,
			SelectorGroupCount: 128,
			TitleTimerTick:     -123, HasTitleTimerTick: true,
		},
	)
	if err != nil {
		t.Fatal(err)
	}
	return input
}

func continueRuntimeUnitsState(
	t *testing.T,
	input fdsave.ContinueRuntimeInput,
) *battle.State {
	t.Helper()
	state := continueFieldBoundaryState()
	if err := MaterializeNativeContinueFieldBoundary(state, input, 1); err != nil {
		t.Fatal(err)
	}
	return state
}

func nativeRuntimeCatalog(t *testing.T) *NativeCharacterCatalog {
	t.Helper()
	catalog, err := LoadNativeCharacterCatalog(
		"../../assets/data/native_character_catalog.json",
	)
	if err != nil {
		t.Fatal(err)
	}
	return catalog
}

func TestMaterializeNativeContinueRuntimeUnitsPreservesRawRoster(t *testing.T) {
	input := continueRuntimeUnitsInput(t, nil)
	state := continueRuntimeUnitsState(t, input)
	if err := MaterializeNativeContinueRuntimeUnits(
		state, input, nativeRuntimeCatalog(t),
	); err != nil {
		t.Fatal(err)
	}
	if !state.HasNativeRuntimeUnitProjection || len(state.Units) != 3 ||
		state.NativeMapSelectorCache == nil {
		t.Fatalf("runtime projection state=%#v", state)
	}
	gotSlots := []int{
		state.Units[0].MapSelectorSlot,
		state.Units[1].MapSelectorSlot,
		state.Units[2].MapSelectorSlot,
	}
	if !reflect.DeepEqual(gotSlots, []int{0, 1, 1}) {
		t.Fatalf("selector slots=%v, want [0 1 1]", gotSlots)
	}
	own := state.Units[0]
	if own.Name != "悠妮" || own.Camp != battle.Own ||
		!own.HasNativeIdentity || own.NativeIdentity != 9 ||
		!own.HasNativeRecordByte8 || own.NativeRecordByte8 != 9 ||
		own.MapSelectorKey != 9 || own.BattleFig != 9 ||
		own.MapSelectorSlot == int(input.RuntimeRecords[0].Raw.Raw[2]) ||
		own.NativeMapPresentation.Motion != 1 ||
		own.NativeTransient != [6]byte{1, 2, 3, 4, 5, 6} ||
		own.NativeRecordWord42 != 14 || own.NativeRecordWord46 != 16 ||
		len(own.Inventory) != 1 || own.Inventory[0] != 0x12 ||
		!own.Equipped[0] {
		t.Fatalf("own runtime unit=%#v", own)
	}
	inactive := state.Units[1]
	if inactive.OnField || inactive.HasNativeIdentity ||
		inactive.NativeRecordByte8 != 0x60 ||
		inactive.NativeMapPresentation.X != 0xff ||
		inactive.NativeMapPresentation.Pose != 0xfd {
		t.Fatalf("inactive runtime unit=%#v", inactive)
	}
	if state.HasNativeMapCycleState || state.HasNativeTerrainPhaseState ||
		state.HasNativeMapBinaryTimingState {
		t.Fatal("runtime unit projection guessed unresolved map timing")
	}

	rawRecords, err := battle.NativeAIScoringRecords(state.Units)
	if err != nil {
		t.Fatal(err)
	}
	if rawRecords[8] != 9 || rawRecords[0x50+8] != 0x60 {
		t.Fatalf("raw +8 projection was lost: %x %x", rawRecords[8], rawRecords[0x58])
	}
}

func TestMaterializeNativeContinueRuntimeUnitsRejectsAtomically(t *testing.T) {
	tests := map[string]func([]fdsave.PersistentRecord){
		"unknown camp": func(records []fdsave.PersistentRecord) {
			records[2].Raw[6] = 3
		},
		"unknown class": func(records []fdsave.PersistentRecord) {
			records[2].Raw[0x20] = 0xff
		},
	}
	for name, mutate := range tests {
		t.Run(name, func(t *testing.T) {
			input := continueRuntimeUnitsInput(t, mutate)
			state := continueRuntimeUnitsState(t, input)
			beforeUnits := state.Units
			if err := MaterializeNativeContinueRuntimeUnits(
				state, input, nativeRuntimeCatalog(t),
			); err == nil {
				t.Fatal("invalid runtime roster was accepted")
			}
			if !reflect.DeepEqual(state.Units, beforeUnits) ||
				state.NativeMapSelectorCache != nil ||
				state.HasNativeRuntimeUnitProjection {
				t.Fatalf("failed runtime projection mutated state=%#v", state)
			}
		})
	}
}
