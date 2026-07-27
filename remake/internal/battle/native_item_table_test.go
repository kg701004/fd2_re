package battle

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadTrackedNativeItemEffectRowPrefix(t *testing.T) {
	rows, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	if got, want := len(rows), 0xd7; got != want {
		t.Fatalf("row count = %d, want %d", got, want)
	}
	if got, want := rows[0], []byte{
		0x01, 0x0a, 0x00, 0x5f, 0x00, 0x00, 0x00, 0x00,
		0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x00, 0x00,
		0x00, 0x05, 0x00, 0x32, 0x00, 0x05, 0x00,
	}; string(got) != string(want) {
		t.Fatalf("row 0 = %x, want %x", got, want)
	}
}

func TestLoadNativeItemEffectRowPrefixRejectsNonConsecutiveID(t *testing.T) {
	path := filepath.Join(t.TempDir(), "rows.json")
	raw := `[{"id":1,"raw":"0000000000000000000000000000000000000000000000"}]`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	if _, err := LoadNativeItemEffectRowPrefix(path); err == nil {
		t.Fatal("expected non-consecutive id error")
	}
}
