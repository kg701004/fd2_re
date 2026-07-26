package fdother

import "testing"

func TestNormalizeNativePreparationKeyPreserves32004Branches(t *testing.T) {
	for _, tc := range []struct {
		name     string
		raw53a8d byte
		raw53a8e byte
		want     byte
	}{
		{"extended-e0", 0x20, 0xe0, 0xe0},
		{"extended-52", 0x20, 0x52, 0x52},
		{"space-record", 0x20, 0x10, 0x1c},
		{"53-overrides-space", 0x20, 0x53, 1},
		{"seed-default", 0x00, 0x10, 0x10},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if got := NormalizeNativePreparationKey(tc.raw53a8d, tc.raw53a8e); got != tc.want {
				t.Fatalf("NormalizeNativePreparationKey(%#x, %#x) = %#x, want %#x", tc.raw53a8d, tc.raw53a8e, got, tc.want)
			}
		})
	}
}
