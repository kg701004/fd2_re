package campaign

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func nativeClassConfirmCells() []fdother.RawCell {
	cells := make([]fdother.RawCell, 53)
	for _, index := range []int{16, 17, 48, 49, 51, 52} {
		height := 16
		if index == 16 || index == 17 {
			height = 20
		}
		cells[index] = fdother.RawCell{Width: 24, Height: height, Pixels: make([]byte, 24*height)}
		for i := range cells[index].Pixels {
			cells[index].Pixels[i] = byte(index)
		}
	}
	return cells
}

func TestNativeClassConfirmationOpenCloseCoordinates(t *testing.T) {
	background := make([]byte, 320*200)
	cells := nativeClassConfirmCells()
	open, err := NativeClassConfirmationOpeningFrames(background, cells)
	if err != nil {
		t.Fatal(err)
	}
	if len(open) != 4 {
		t.Fatalf("open frames=%d", len(open))
	}
	for i, spread := range []int{4, 8, 12, 16} {
		if open[i][168*320+248-spread] != 16 || open[i][168*320+248+spread] != 17 {
			t.Fatalf("open frame%d spread%d mismatch", i, spread)
		}
	}
	closeFrames, err := NativeClassConfirmationClosingFrames(background, cells)
	if err != nil {
		t.Fatal(err)
	}
	for i, spread := range []int{12, 8, 4, 0} {
		if spread == 0 {
			if closeFrames[i][168*320+248] != 17 {
				t.Fatalf("close frame%d overlap did not preserve second-cell overwrite", i)
			}
			continue
		}
		if closeFrames[i][168*320+248-spread] != 16 || closeFrames[i][168*320+248+spread] != 17 {
			t.Fatalf("close frame%d spread%d mismatch", i, spread)
		}
	}
}

func TestComposeNativeClassConfirmationExpandsNameAndSelection(t *testing.T) {
	strings := nativeClassListStrings(t)
	frame, err := ComposeNativeClassConfirmationFrame(
		make([]byte, 320*200), nativeClassConfirmCells(),
		strings, nativeClassListFont(t), 1, 1, 1,
	)
	if err != nil {
		t.Fatal(err)
	}
	if got := frame[119*320+12]; got != 205 {
		t.Fatalf("dynamic name foreground=%d want 205", got)
	}
	if got := frame[168*320+232]; got != 48 {
		t.Fatalf("option0 cell=%d want 48", got)
	}
	if got := frame[168*320+264]; got != 52 {
		t.Fatalf("selected option1 pulse cell=%d want 52", got)
	}
}
