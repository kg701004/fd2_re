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

	// NativeCommandGridVisibleColumns is a deliberate remake-only QoL
	// addition (user request): the original 0x1ceed layout was never
	// designed to scroll, because no native unit ever had more than a
	// handful of set command bits. Once a unit can hold up to all 36
	// defined commands (e.g. via the QoL skill-bit injection discussed
	// earlier this session), columns beyond the 320px-wide screen
	// (X=0x12 + 3*0x64 = 0x14e = 318, right at the edge) would render off
	// screen with no way to reach them. NativeCommandGridWindow adds
	// scrolling so every held command stays reachable.
	NativeCommandGridVisibleColumns = 3
	NativeCommandGridVisible        = NativeCommandGridRows * NativeCommandGridVisibleColumns
)

// NativeCommandGridWindow computes the scrolling window's start index (a
// multiple of NativeCommandGridRows, keeping column alignment) and visible
// count so that `selected` always stays on screen. Mirrors the shape of
// campaign.NativeTwoColumnWindow but steps by whole columns instead of
// row-pairs, since this grid scrolls horizontally by column.
func NativeCommandGridWindow(count, selected, start int) (nextStart, visible int) {
	if count <= 0 || selected < 0 || selected >= count || start < 0 || start%NativeCommandGridRows != 0 {
		return 0, 0
	}
	maxStart := count - NativeCommandGridVisible
	if maxStart < 0 {
		maxStart = 0
	}
	if r := maxStart % NativeCommandGridRows; r != 0 {
		maxStart += NativeCommandGridRows - r
	}
	if start > maxStart {
		start = maxStart
	}
	for selected < start && start >= NativeCommandGridRows {
		start -= NativeCommandGridRows
	}
	for selected >= start+NativeCommandGridVisible && start < maxStart {
		start += NativeCommandGridRows
	}
	visible = count - start
	if visible > NativeCommandGridVisible {
		visible = NativeCommandGridVisible
	}
	return start, visible
}

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
