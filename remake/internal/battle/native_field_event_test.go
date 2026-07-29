package battle

import (
	"path/filepath"
	"reflect"
	"testing"
)

func TestNativeFieldEventIDAtMatchesSelector(t *testing.T) {
	st := &State{
		W: 2, H: 2,
		NativeFieldEventSlots: []int{-1, 3, -1, -1},
		NativeFieldEvents:     make([]NativeFieldEvent, 16),
	}
	st.NativeFieldEvents[3] = NativeFieldEvent{EventID: 82, Selector: 1}
	if got, ok := NativeFieldEventIDAt(st, 1, 0, 1); !ok || got != 82 {
		t.Fatalf("event = (%d,%v), want (82,true)", got, ok)
	}
	if _, ok := NativeFieldEventIDAt(st, 1, 0, 0); ok {
		t.Fatal("selector mismatch unexpectedly accepted")
	}
}

func TestNativeFieldEventIDAtFailsClosed(t *testing.T) {
	st := &State{W: 1, H: 1, NativeFieldEventSlots: []int{0}}
	if _, ok := NativeFieldEventIDAt(st, 0, 0, 0); ok {
		t.Fatal("missing table unexpectedly accepted")
	}
	st.NativeFieldEvents = make([]NativeFieldEvent, 16)
	st.NativeFieldEvents[0] = NativeFieldEvent{EventID: 0xff}
	if _, ok := NativeFieldEventIDAt(st, 0, 0, 0); ok {
		t.Fatal("0xff event unexpectedly accepted")
	}
}

func TestAllEditableMapsCarryNativeRendererInputs(t *testing.T) {
	paths, err := filepath.Glob("../../assets/maps/map*/map*_units.json")
	if err != nil {
		t.Fatal(err)
	}
	if len(paths) != 33 {
		t.Fatalf("map unit assets=%d, want 33", len(paths))
	}
	for _, path := range paths {
		st, err := Load(path)
		if err != nil {
			t.Fatalf("%s: %v", path, err)
		}
		if len(st.NativeTileBlitModes) != st.W*st.H ||
			len(st.NativeTerrainControl) == 0 ||
			len(st.NativeTerrainControl)%4 != 0 {
			t.Fatalf(
				"%s: renderer modes=%d cells=%d controls=%d",
				path, len(st.NativeTileBlitModes), st.W*st.H,
				len(st.NativeTerrainControl),
			)
		}
	}
}

func TestMap25LoadsEditableNativeFieldEventRules(t *testing.T) {
	st, err := Load("../../assets/maps/map25/map25_units.json")
	if err != nil {
		t.Fatal(err)
	}
	if len(st.NativeFieldEventRules) != 3 {
		t.Fatalf("field event rules=%d, want 3", len(st.NativeFieldEventRules))
	}
	if got := st.NativeFieldEventRules[0]; got.EventID != 59 || got.Selector != 0 ||
		got.TriggerGate != "record_byte6_nonzero" ||
		!reflect.DeepEqual(got.SetModeRanges, []NativeFieldModeRange{{Start: 39, End: 44, Mode: 0}}) {
		t.Fatalf("event59 rule=%#v", got)
	}
	got61 := st.NativeFieldEventRules[2]
	if got61.EventID != 61 || got61.Selector != 1 ||
		got61.OnceState == nil || *got61.OnceState != 12 ||
		got61.RequiredItem == nil || *got61.RequiredItem != 0xD0 ||
		got61.SpawnGroup == nil || *got61.SpawnGroup != 1 ||
		got61.JoinCharacter == nil || *got61.JoinCharacter != 31 ||
		got61.TextIndices == nil ||
		*got61.TextIndices != (NativeFieldTextIndices{MissingItem: 2, Success: 3, Final: 4}) ||
		got61.Presentation == nil ||
		*got61.Presentation != (NativeFieldPresentation{
			Archive: "FDOTHER.DAT", Resource: 45, Frames: 59,
			Helper: "0x2935b", DestinationOffset: 48356, Stride: 320,
			Transparent: -1, DelayHelper: "0x17aa9", DelayTicks: 2,
		}) {
		t.Fatalf("event61 rule=%#v", got61)
	}
}

func TestChapter26KeepsWoldPendingUntilEvent61(t *testing.T) {
	st, err := Load("../../assets/maps/map25/map25_units.json")
	if err != nil {
		t.Fatal(err)
	}
	sc, err := LoadScenario("../../assets/scenarios/ch26.json")
	if err != nil {
		t.Fatal(err)
	}
	if !sc.RuntimeAppendGroups || !reflect.DeepEqual(sc.InitialGroups, []int{0}) {
		t.Fatalf("ch26 constructor policy: runtime=%v initial=%v", sc.RuntimeAppendGroups, sc.InitialGroups)
	}
	sc.Setup(st)
	var activeWold, pendingWold int
	for _, unit := range st.Units {
		if unit != nil && unit.Group == 1 && unit.Fig == 31 {
			activeWold++
		}
	}
	for _, unit := range st.Roster {
		if unit != nil && unit.Group == 1 && unit.Fig == 31 {
			pendingWold++
		}
	}
	if activeWold != 0 || pendingWold != 1 {
		t.Fatalf("event61 前渥德 active=%d pending=%d", activeWold, pendingWold)
	}
}

func setupChapter26Event61(t *testing.T, items ...int) (*State, *Unit) {
	t.Helper()
	st, err := Load("../../assets/maps/map25/map25_units.json")
	if err != nil {
		t.Fatal(err)
	}
	sc, err := LoadScenario("../../assets/scenarios/ch26.json")
	if err != nil {
		t.Fatal(err)
	}
	sc.Setup(st)
	trigger := st.Units[0]
	trigger.X, trigger.Y = 1, 46
	trigger.Inventory = append([]int(nil), items...)
	trigger.Equipped = make([]bool, len(items))
	trigger.InventorySlots = make([]int, 8)
	trigger.NativeInventoryFlags = make([]int, 8)
	for i := range trigger.InventorySlots {
		trigger.InventorySlots[i] = 0xff
		trigger.NativeInventoryFlags[i] = 0x80
	}
	for i, item := range items {
		trigger.InventorySlots[i] = item
		trigger.NativeInventoryFlags[i] = 0
	}
	return st, trigger
}

func TestEvent61MissingItemPlansOnlyOriginalText(t *testing.T) {
	st, trigger := setupChapter26Event61(t, 0x20)
	plan, err := PlanNativeFieldEvent61(st, trigger, 1, 46)
	if err != nil {
		t.Fatal(err)
	}
	if !plan.MissingItem || plan.TextIndex != 2 || plan.FinalText != 4 {
		t.Fatalf("missing-item plan=%#v", plan)
	}
	if st.NativeEventState[12] != 0 || len(st.Roster) == 0 ||
		len(trigger.Inventory) != 1 || trigger.Inventory[0] != 0x20 {
		t.Fatal("missing-item planning mutated battle state")
	}
	if _, err := CommitNativeFieldEvent61(st, plan, 59); err == nil {
		t.Fatal("missing-item plan unexpectedly committed")
	}
}

func TestEvent61CommitsAfterAllFramesAndReturnsJoin(t *testing.T) {
	st, trigger := setupChapter26Event61(t, 0xD0, 0x20)
	plan, err := PlanNativeFieldEvent61(st, trigger, 1, 46)
	if err != nil {
		t.Fatal(err)
	}
	if plan.MissingItem || plan.TextIndex != 3 || plan.FinalText != 4 ||
		plan.Presentation.Frames != 59 {
		t.Fatalf("success plan=%#v", plan)
	}
	if _, err := CommitNativeFieldEvent61(st, plan, 58); err == nil {
		t.Fatal("incomplete presentation unexpectedly committed")
	}
	if st.NativeEventState[12] != 0 || trigger.Inventory[0] != 0xD0 {
		t.Fatal("failed commit partially mutated state")
	}
	joined, err := CommitNativeFieldEvent61(st, plan, 59)
	if err != nil {
		t.Fatal(err)
	}
	if joined != 31 || st.NativeEventState[12] != 1 ||
		!reflect.DeepEqual(trigger.Inventory, []int{0x20}) ||
		trigger.InventorySlots[0] != 0x20 ||
		trigger.InventorySlots[1] != 0xff {
		t.Fatalf("event61 commit join=%d state=%d inventory=%v slots=%v",
			joined, st.NativeEventState[12], trigger.Inventory, trigger.InventorySlots)
	}
	var activeWold, pendingWold int
	for _, unit := range st.Units {
		if unit != nil && unit.Group == 1 && unit.Fig == 31 && unit.OnField {
			activeWold++
		}
	}
	for _, unit := range st.Roster {
		if unit != nil && unit.Group == 1 && unit.Fig == 31 {
			pendingWold++
		}
	}
	if activeWold != 1 || pendingWold != 0 {
		t.Fatalf("event61 後渥德 active=%d pending=%d", activeWold, pendingWold)
	}
}

func TestEvent61RevalidatesInventoryBeforeCommit(t *testing.T) {
	st, trigger := setupChapter26Event61(t, 0xD0)
	plan, err := PlanNativeFieldEvent61(st, trigger, 1, 46)
	if err != nil {
		t.Fatal(err)
	}
	trigger.Inventory[0], trigger.InventorySlots[0] = 0x20, 0x20
	if _, err := CommitNativeFieldEvent61(st, plan, 59); err == nil {
		t.Fatal("changed inventory unexpectedly committed")
	}
	if st.NativeEventState[12] != 0 || len(st.Roster) == 0 {
		t.Fatal("revalidation failure partially mutated state")
	}
}

func TestMap25Event59AppliesModeRangeAtomically(t *testing.T) {
	st, err := Load("../../assets/maps/map25/map25_units.json")
	if err != nil {
		t.Fatal(err)
	}
	trigger := &Unit{NativeRecordByte6: 1, HasNativeRecordByte6: true}
	for index := 39; index <= 44; index++ {
		st.Units[index].NativeRecordByte34 |= 0xA0
		st.Units[index].HasNativeRecordByte34 = true
	}
	if eventID, ok := ApplyNativeFieldModeEvent(st, trigger, 10, 36, 0); !ok || eventID != 59 {
		t.Fatalf("event59=(%d,%v)", eventID, ok)
	}
	for index := 39; index <= 44; index++ {
		if got := st.Units[index].NativeRecordByte34; got != 0xA0 {
			t.Fatalf("unit%d byte34=%#x, want 0xa0", index, got)
		}
	}
}

func TestNativeFieldModeEventFailsClosedBeforePartialWrite(t *testing.T) {
	st, err := Load("../../assets/maps/map25/map25_units.json")
	if err != nil {
		t.Fatal(err)
	}
	trigger := &Unit{NativeRecordByte6: 1, HasNativeRecordByte6: true}
	before := st.Units[23].NativeRecordByte34
	st.Units[56].HasNativeRecordByte34 = false
	if _, ok := ApplyNativeFieldModeEvent(st, trigger, 10, 22, 0); ok {
		t.Fatal("incomplete event60 target provenance unexpectedly accepted")
	}
	if st.Units[23].NativeRecordByte34 != before {
		t.Fatal("event60 partially mutated before validation completed")
	}
}
