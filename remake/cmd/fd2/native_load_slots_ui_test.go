package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestNativeLoadSlotMetadataPreservesEmptyAndRawChapter(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_DATA_HOME", root)
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
}

func TestNativeLoadSlotMetadataRejectsUnmappableJSON(t *testing.T) {
	root := t.TempDir()
	t.Setenv("XDG_DATA_HOME", root)
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
