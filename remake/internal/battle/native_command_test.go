package battle

import (
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
	if err := os.WriteFile(path, []byte(`{"map":0,"w":1,"h":1,"units":[{"camp":"enemy","hp":1,"initial_command_mask":[1,0,0,128]}]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	st, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if got, want := st.Units[0].NativeCommandIDs(), []int{0, 31}; !reflect.DeepEqual(got, want) {
		t.Fatalf("loaded IDs=%v want %v", got, want)
	}
	if err := os.WriteFile(path, []byte(`{"map":0,"w":1,"h":1,"units":[{"camp":"enemy","hp":1,"initial_command_mask":[1,2,3]}]}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("malformed initial command mask loaded")
	}
}
