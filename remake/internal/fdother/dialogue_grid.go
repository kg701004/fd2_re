package fdother

import "fmt"

// NativeDialogueGridPlacement is one 0x168b6 -> 0x1685c raw-cell copy.
type NativeDialogueGridPlacement struct {
	ResourceIndex   int
	DestinationByte int
}

// PlanNativeDialogueFrameGrid transcribes 0x168b6 for explicit caller
// arguments. The destination offset includes both x and y origins.
func PlanNativeDialogueFrameGrid(stride, x, y, columns, rows int) ([]NativeDialogueGridPlacement, error) {
	if stride <= 0 || x < 0 || y < 0 || columns < 2 || rows < 2 ||
		x >= stride || columns > (stride-x)/16 {
		return nil, fmt.Errorf(
			"fdother: native dialogue grid %d/%d,%d/%dx%d is invalid",
			stride, x, y, columns, rows,
		)
	}

	base := y*stride + x
	cellRowStride := 16 * stride
	placements := make([]NativeDialogueGridPlacement, 0, 12+2*(columns-2)+2*(rows-2)+columns*rows)
	add := func(index, offset int) {
		placements = append(placements, NativeDialogueGridPlacement{
			ResourceIndex: index, DestinationByte: offset,
		})
	}

	add(1, base)
	add(2, base+3+16*columns)
	add(3, base+3*stride+rows*cellRowStride)
	add(4, base+3*stride+rows*cellRowStride+16*columns+3)
	add(5, base+3)
	add(6, base+19+16*(columns-2))
	add(7, base+3*stride+rows*cellRowStride+3)
	add(8, base+3*stride+rows*cellRowStride+19+16*(columns-2))
	add(14, base+3*stride)
	rightMiddle := base + 3*stride + 35 + 16*(columns-2)
	add(15, rightMiddle)
	lowerMiddle := (rows-2+1)*cellRowStride + base + 3*stride
	add(16, lowerMiddle)
	add(17, (rows-2+1)*cellRowStride+rightMiddle)

	for column := 0; column < columns-2; column++ {
		add(9, base+19+16*column)
		add(12, base+3*stride+rows*cellRowStride+19+16*column)
	}
	for row := 0; row < rows-2; row++ {
		left := base + 3*stride + (row+1)*cellRowStride
		add(10, left)
		add(11, left+16*columns+3)
	}
	for row := 0; row < rows; row++ {
		for column := 0; column < columns; column++ {
			add(13, base+3*stride+3+row*cellRowStride+16*column)
		}
	}
	return placements, nil
}
