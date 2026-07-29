package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdsave"
)

func TestNativeLoadSlotMetadataPreservesEmptyAndRawChapter(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_DATA_HOME", root)
	t.Setenv("FD2_NATIVE_SAVE", "")
	userDataDirCached = ""
	t.Cleanup(func() { userDataDirCached = "" })
	path := saveSlotPath(1)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	raw, err := json.Marshal(saveData{Node: "town_ch08", Chapter: 7})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	slots, ok := nativeLoadSlotMetadata()
	if !ok {
		t.Fatal("valid remake slot metadata rejected")
	}
	if !slots[0].Empty || slots[1].Empty || slots[1].Chapter != 7 ||
		!slots[2].Empty || !slots[3].Empty {
		t.Fatalf("slots=%#v", slots)
	}
	if confirmable, native := nativeLoadSlotConfirmable(1); !confirmable || native {
		t.Fatalf("JSON valid confirm=(%v,%v)", confirmable, native)
	}
	if confirmable, native := nativeLoadSlotConfirmable(0); confirmable || native {
		t.Fatalf("JSON empty confirm=(%v,%v)", confirmable, native)
	}
}

func TestNativeLoadSlotMetadataRejectsUnmappableJSON(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_DATA_HOME", root)
	t.Setenv("FD2_NATIVE_SAVE", "")
	userDataDirCached = ""
	t.Cleanup(func() { userDataDirCached = "" })
	path := saveSlotPath(0)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(`{"chapter":0}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if got, ok := nativeLoadSlotMetadata(); ok {
		t.Fatalf("unmappable metadata accepted: %#v", got)
	}
}

func TestNativeLoadSlotMetadataReadsVerifiedNativeEnvelope(t *testing.T) {
	plain := make([]byte, fdsave.FileSize)
	for slot := 0; slot < fdsave.SlotCount; slot++ {
		start, _, err := fdsave.SlotBounds(slot)
		if err != nil {
			t.Fatal(err)
		}
		plain[start+fdsave.RosterSize] = 0xff
	}
	start, _, err := fdsave.SlotBounds(2)
	if err != nil {
		t.Fatal(err)
	}
	plain[start+fdsave.RosterSize] = 7
	stored, err := fdsave.Encode(plain)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "FD2.SAV")
	if err := os.WriteFile(path, stored, 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("FD2_NATIVE_SAVE", path)

	slots, ok := nativeLoadSlotMetadata()
	if !ok || !slots[0].Empty || !slots[1].Empty ||
		slots[2].Empty || slots[2].Chapter != 7 || !slots[3].Empty {
		t.Fatalf("native slots=%#v ok=%v", slots, ok)
	}
	if confirmable, native := nativeLoadSlotConfirmable(2); !confirmable || !native {
		t.Fatalf("native valid confirm=(%v,%v)", confirmable, native)
	}
	if confirmable, native := nativeLoadSlotConfirmable(0); confirmable || !native {
		t.Fatalf("native empty confirm=(%v,%v)", confirmable, native)
	}
}

func TestNativeLoadSlotMetadataRejectsTamperedNativeEnvelope(t *testing.T) {
	stored, err := fdsave.Encode(make([]byte, fdsave.FileSize))
	if err != nil {
		t.Fatal(err)
	}
	stored[0x123] ^= 1
	path := filepath.Join(t.TempDir(), "FD2.SAV")
	if err := os.WriteFile(path, stored, 0o644); err != nil {
		t.Fatal(err)
	}
	t.Setenv("FD2_NATIVE_SAVE", path)
	if got, ok := nativeLoadSlotMetadata(); ok {
		t.Fatalf("tampered native save accepted: %#v", got)
	}
}

func TestParseNativeLoadSlotShotStateIsBounded(t *testing.T) {
	for _, value := range []string{"0", "1", "2", "3"} {
		if _, ok := parseNativeLoadSlotShotState(value); !ok {
			t.Fatalf("valid selection %q rejected", value)
		}
	}
	for _, value := range []string{"", "-1", "4", "x"} {
		if got, ok := parseNativeLoadSlotShotState(value); ok {
			t.Fatalf("invalid selection %q accepted as %d", value, got)
		}
	}
}
