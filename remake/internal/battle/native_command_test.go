package battle

import (
	"math/rand"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestNativeCommandMaskConstructorAndDynamicFifthByte(t *testing.T) {
	u := &Unit{}
	if err := u.SetInitialCommandMask([]byte{0x81, 0x01, 0x00, 0x80}); err != nil {
		t.Fatal(err)
	}
	if got, want := u.NativeCommandIDs(), []int{0, 7, 8, 31}; !reflect.DeepEqual(got, want) {
		t.Fatalf("initial IDs=%v want %v", got, want)
	}
	if !u.EnableNativeCommand(32) || !u.EnableNativeCommand(39) || u.EnableNativeCommand(40) {
		t.Fatalf("fifth-byte command bounds failed: %#v", u.NativeCommandMask)
	}
	if got, want := u.NativeCommandIDs(), []int{0, 7, 8, 31, 32, 39}; !reflect.DeepEqual(got, want) {
		t.Fatalf("expanded IDs=%v want %v", got, want)
	}
}

func TestStateGainExpLearnsExactNativeCommandAtLevel(t *testing.T) {
	u := &Unit{Camp: Own, Name: "索爾", ClsName: "劍士", Portrait: 0, Lv: 1, AP: 6, DP: 4, DX: 2, HP: 42, MaxHP: 42}
	st := &State{CommandLearn: map[int][]CommandLearnEntry{0: {{RequiredLevel: 2, CommandID: 32}}}}
	events := st.GainExp(u, 100, rand.New(rand.NewSource(1)))
	if len(events) != 1 || !reflect.DeepEqual(events[0].LearnedCommandIDs, []int{32}) {
		t.Fatalf("level-up learning events=%#v", events)
	}
	if got := u.NativeCommandIDs(); !reflect.DeepEqual(got, []int{32}) {
		t.Fatalf("native command mask after level=%v", got)
	}
}

func TestLoadCommandLearnUsesDenseNativeRows(t *testing.T) {
	table, err := LoadCommandLearn("../../../docs/data/exe_tables/command_learn.json")
	if err != nil {
		t.Fatal(err)
	}
	if got := table[0]; len(table) != 20 || !reflect.DeepEqual(got[:2], []CommandLearnEntry{{RequiredLevel: 5, CommandID: 17}, {RequiredLevel: 9, CommandID: 1}}) {
		t.Fatalf("native learn table=%#v", table[0])
	}
}

func TestNativeCommandMaskRejectsMalformedSourceWithoutMutation(t *testing.T) {
	u := &Unit{NativeCommandMask: [5]byte{1, 2, 3, 4, 5}}
	if err := u.SetInitialCommandMask([]byte{1, 2, 3}); err == nil {
		t.Fatal("short source mask accepted")
	}
	if got, want := u.NativeCommandMask, [5]byte{1, 2, 3, 4, 5}; got != want {
		t.Fatalf("malformed source mutated mask: %v", got)
	}
}

func TestLoadMaterializesFDFIELDInitialCommandMask(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "units.json")
	if err := os.WriteFile(path, []byte(`{"map":0,"w":1,"h":1,"units":[{"camp":"enemy","hp":1,"map_selector_key":0,"native_record_byte5":128,"native_record_byte34":130,"native_record_byte35":18,"native_record_byte36":7,"initial_command_mask":[1,0,0,128]}]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	st, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got, want := st.Units[0].NativeCommandIDs(), []int{0, 31}; !reflect.DeepEqual(got, want) {
		t.Fatalf("loaded IDs=%v want %v", got, want)
	}
	if !st.Units[0].HasNativeRecordByte5 || st.Units[0].NativeRecordByte5 != 0x80 || !st.Units[0].HasNativeRecordByte6 || st.Units[0].NativeRecordByte6 != 0 {
		t.Fatalf("loaded raw record bytes=%#x/%v %#x/%v", st.Units[0].NativeRecordByte5, st.Units[0].HasNativeRecordByte5, st.Units[0].NativeRecordByte6, st.Units[0].HasNativeRecordByte6)
	}
	if !st.Units[0].HasNativeRecordByte34 || st.Units[0].NativeRecordByte34 != 0x82 ||
		!st.Units[0].HasNativeRecordByte35 || st.Units[0].NativeRecordByte35 != 0x12 ||
		!st.Units[0].HasNativeRecordByte36 || st.Units[0].NativeRecordByte36 != 7 {
		t.Fatalf("loaded native mode bytes=%#x/%v %#x/%v %#x/%v",
			st.Units[0].NativeRecordByte34, st.Units[0].HasNativeRecordByte34,
			st.Units[0].NativeRecordByte35, st.Units[0].HasNativeRecordByte35,
			st.Units[0].NativeRecordByte36, st.Units[0].HasNativeRecordByte36)
	}
	if err := os.WriteFile(path, []byte(`{"map":0,"w":1,"h":1,"units":[{"camp":"enemy","hp":1,"initial_command_mask":[1,2,3]}]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("malformed initial command mask loaded")
	}
}
