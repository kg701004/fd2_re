package fdother

import "testing"

func TestMapIndexFromAssetPathRequiresExactMapBinding(t *testing.T) {
	for _, tc := range []struct {
		path string
		want int
	}{
		{"assets", 0}, {"assets/maps/map0", 0}, {"assets/maps/map32", 32},
	} {
		got, err := MapIndexFromAssetPath(tc.path)
		if err != nil || got != tc.want {
			t.Fatalf("%q: got %d, %v", tc.path, got, err)
		}
	}
	for _, path := range []string{"assets/maps/map", "assets/maps/map01x", "assets/maps/map-1", "assets/maps/other"} {
		if _, err := MapIndexFromAssetPath(path); err == nil {
			t.Fatalf("%q accepted", path)
		}
	}
}
