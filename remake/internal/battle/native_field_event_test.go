package battle

import (
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
