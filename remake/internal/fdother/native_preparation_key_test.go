package fdother

import "testing"

func TestNormalizeNativePreparationKeyPreserves32004Branches(t *testing.T) {
	for _, tc := range []struct {
		name     string
		raw53a8d byte
		raw53a8e byte
		want     byte
	}{
		{"extended-e0", 0x00, 0xe0, 0x1c},
		{"extended-52", 0x00, 0x52, 0x1c},
		{"space-record", 0x20, 0x10, 0x1c},
		{"53-without-space", 0x00, 0x53, 1},
		{"space-precedes-53", 0x20, 0x53, 0x1c},
		{"seed-default", 0x00, 0x10, 0x10},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if got := NormalizeNativePreparationKey(tc.raw53a8d, tc.raw53a8e); got != tc.want {
				t.Fatalf("NormalizeNativePreparationKey(%#x, %#x) = %#x, want %#x", tc.raw53a8d, tc.raw53a8e, got, tc.want)
			}
		})
	}
}
