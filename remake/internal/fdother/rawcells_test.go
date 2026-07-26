package fdother

import (
	"encoding/binary"
	"os"
	"testing"
)

func rawCellBank(cells ...[]byte) []byte {
	directoryEnd := len(cells) * 4
	data := make([]byte, directoryEnd)
	off := directoryEnd
	for i, cell := range cells {
		binary.LittleEndian.PutUint32(data[4*i:], uint32(off))
		data = append(data, cell...)
		off += len(cell)
	}
	return data
}

func rawCell(width, height int, pixels ...byte) []byte {
	data := make([]byte, 4)
	binary.LittleEndian.PutUint16(data, uint16(width))
	binary.LittleEndian.PutUint16(data[2:], uint16(height))
	return append(data, pixels...)
}

func TestRawCellBankPreservesTransparentPixels(t *testing.T) {
	cells, err := ParseRawCellBank(rawCellBank(rawCell(3, 1, 1, 0, 2), rawCell(1, 1, 7)))
	if err != nil {
		t.Fatal(err)
	}
	if len(cells) != 2 || cells[0].Width != 3 || cells[1].Pixels[0] != 7 {
		t.Fatalf("cells=%#v", cells)
	}
	dst := make([]byte, 8)
	for i := range dst {
		dst[i] = 9
	}
	if err := cells[0].BlitAt(dst, 8, 2, 0); err != nil {
		t.Fatal(err)
	}
	if got, want := dst[:6], []byte{9, 9, 1, 9, 2, 9}; string(got) != string(want) {
		t.Fatalf("blit=%v, want %v", got, want)
	}
}

func TestRawCellBankRejectsMalformedGeometry(t *testing.T) {
	data := rawCellBank(rawCell(2, 2, 1))
	if _, err := ParseRawCellBank(data); err == nil {
		t.Fatal("truncated raw cell was accepted")
	}
}

func TestRawCellOpaqueOffsetWritesLiteralZero(t *testing.T) {
	dst := []byte{9, 9, 9, 9, 9, 9}
	cell := RawCell{Width: 2, Height: 1, Pixels: []byte{0, 7}}
	if err := cell.BlitOpaqueAtOffset(dst, 3, 1); err != nil {
		t.Fatal(err)
	}
	if got, want := dst, []byte{9, 0, 7, 9, 9, 9}; string(got) != string(want) {
		t.Fatalf("opaque offset=%v, want %v", got, want)
	}
}

func TestFDOTHER002ActionOverlayCells(t *testing.T) {
	const path = "../../../extracted/raw/FDOTHER/FDOTHER_002.bin"
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		t.Skip("player-provided FDOTHER_002 asset is absent")
	}
	if err != nil {
		t.Fatal(err)
	}
	cells, err := ParseRawCellBank(data)
	if err != nil {
		t.Fatal(err)
	}
	if len(cells) != 78 {
		t.Fatalf("FDOTHER#2 cell count=%d, want 78", len(cells))
	}
	short := 0
	for i, cell := range cells {
		if cell.Width != 24 || (cell.Height != 20 && cell.Height != 16) || len(cell.Pixels) != cell.Width*cell.Height {
			t.Fatalf("FDOTHER#2 cell %d=%dx%d pixels=%d", i, cell.Width, cell.Height, len(cell.Pixels))
		}
		if cell.Height == 16 {
			short++
		}
		if err := cell.BlitAt(make([]byte, 320*200), 320, 0, 0); err != nil {
			t.Fatalf("FDOTHER#2 cell %d blit: %v", i, err)
		}
	}
	if short != 4 {
		t.Fatalf("FDOTHER#2 24x16 cell count=%d, want 4", short)
	}
}
