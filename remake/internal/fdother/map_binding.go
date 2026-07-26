package fdother

import (
	"errors"
	"path/filepath"
	"strconv"
	"strings"
)

// MapIndexFromAssetPath accepts only the exported tactical-map locations.
// `assets` is the documented legacy alias for map0; all other accepted paths
// end in exactly `mapN`. This is a binding, not a filename heuristic.
func MapIndexFromAssetPath(path string) (int, error) {
	base := filepath.Base(filepath.Clean(path))
	if base == "assets" {
		return 0, nil
	}
	if !strings.HasPrefix(base, "map") || len(base) == 3 {
		return 0, errors.New("fdother: map asset path lacks explicit map index")
	}
	index, err := strconv.Atoi(base[3:])
	if err != nil || index < 0 {
		return 0, errors.New("fdother: invalid map asset index")
	}
	return index, nil
}
