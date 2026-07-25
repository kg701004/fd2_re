package battle

// NativeCommandGridCell is one recovered 0x1ceed command-menu cell in the
// original 320×200 coordinate space. The caller supplies command IDs in the
// exact 0x1c269 order; this type intentionally contains no effect semantics.
type NativeCommandGridCell struct {
	CommandID int
	Column    int
	Row       int
	X         int
	Y         int
	Selected  bool
}

const (
	NativeCommandGridX       = 0x12
	NativeCommandGridY       = 0x67
	NativeCommandGridColumnW = 0x64
	NativeCommandGridRowH    = 0x16
	NativeCommandGridRows    = 4
)

// NativeCommandGrid mirrors 0x1ceed's i/4 column and i%4 row placement.
func NativeCommandGrid(ids []int, selected int) []NativeCommandGridCell {
	grid := make([]NativeCommandGridCell, len(ids))
	for i, id := range ids {
		grid[i] = NativeCommandGridCell{
			CommandID: id,
			Column:    i / NativeCommandGridRows,
			Row:       i % NativeCommandGridRows,
			X:         NativeCommandGridX + NativeCommandGridColumnW*(i/NativeCommandGridRows),
			Y:         NativeCommandGridY + NativeCommandGridRowH*(i%NativeCommandGridRows),
			Selected:  i == selected,
		}
	}
	return grid
}

// NativeCommandGridMove implements 0x1d51d navigation. It returns the prior
// index for an invalid horizontal move; up/down wrap only at the list ends.
func NativeCommandGridMove(index, count, direction int) int {
	if count <= 0 || index < 0 || index >= count {
		return -1
	}
	switch direction {
	case 0: // up
		if index == 0 {
			return count - 1
		}
		return index - 1
	case 1: // down
		if index == count-1 {
			return 0
		}
		return index + 1
	case 2: // left
		if index >= NativeCommandGridRows {
			return index - NativeCommandGridRows
		}
	case 3: // right
		if index+NativeCommandGridRows < count {
			return index + NativeCommandGridRows
		}
	}
	return index
}
