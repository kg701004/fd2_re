package fdother

import (
	"encoding/binary"
	"os"
	"testing"
)

func TestParseLMI1NativeCodec(t *testing.T) {
	// Two entries: literal 0, literal 0xc0, then a 0xc3 repeat of 7.
	data := make([]byte, 6+2*4)
	copy(data, "LMI1")
	binary.LittleEndian.PutUint16(data[4:], 2)
	first, second := 14, 22
	binary.LittleEndian.PutUint32(data[6:], uint32(first))
	binary.LittleEndian.PutUint32(data[10:], uint32(second))
	data = append(data, 3, 0, 1, 0, 0, 0xc0, 1, 2)
	data = append(data, 2, 0, 1, 0, 0xc2, 7)
	entries, err := ParseLMI1(data)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 2 || entries[0].Width != 3 || entries[0].Height != 1 {
		t.Fatalf("entries=%#v", entries)
	}
	want0 := []byte{0, 0xc0, 1}
	for i, v := range want0 {
		if entries[0].Pixels[i] != v {
			t.Fatalf("entry0 pixel %d=%#x, want %#x", i, entries[0].Pixels[i], v)
		}
	}
	if entries[1].Width != 2 || entries[1].Height != 1 || len(entries[1].Pixels) != 2 || entries[1].Pixels[0] != 7 || entries[1].Pixels[1] != 7 {
		t.Fatalf("entry1=%#v", entries[1])
	}
}

func TestParseLMI1RejectsMalformedCodec(t *testing.T) {
	data := make([]byte, 14)
	copy(data, "LMI1")
	binary.LittleEndian.PutUint16(data[4:], 1)
	binary.LittleEndian.PutUint32(data[6:], 10)
	binary.LittleEndian.PutUint16(data[10:], 2)
	binary.LittleEndian.PutUint16(data[12:], 1)
	if _, err := ParseLMI1(data); err == nil {
		t.Fatal("truncated LMI1 stream must fail closed")
	}
}

func TestLMI1BlitPreservesTransparentAndMirrors(t *testing.T) {
	e := LMI1Entry{Width: 3, Height: 1, Pixels: []byte{1, 0, 2}}
	dst := make([]byte, 16)
	for i := range dst {
		dst[i] = 9
	}
	if err := e.BlitAt(dst, 8, 1, 0, false); err != nil {
		t.Fatal(err)
	}
	if got, want := dst[:5], []byte{9, 1, 9, 2, 9}; string(got) != string(want) {
		t.Fatalf("forward blit=%v, want %v", got, want)
	}
	if err := e.BlitAt(dst, 8, 1, 1, true); err != nil {
		t.Fatal(err)
	}
	if got, want := dst[8:13], []byte{9, 2, 9, 1, 9}; string(got) != string(want) {
		t.Fatalf("mirrored blit=%v, want %v", got, want)
	}
}

func TestFDOTHER005LMI1UIContainer(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(datPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	entries, err := DecodeLMI1Resource(datPath, 5)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 138 {
		t.Fatalf("FDOTHER#5 LMI1 entry count=%d, want 138", len(entries))
	}
	// Native 0x1f42d selects LMI1 entry #0x52 for its pre-battle split slide.
	if e := entries[0x52]; e.Width != 72 || e.Height != 14 || len(e.Pixels) != 72*14 {
		t.Fatalf("FDOTHER#5 LMI1 entry#0x52=%dx%d pixels=%d, want 72x14", e.Width, e.Height, len(e.Pixels))
	}
}

func TestFDOTHER005MapHUDUses4ModeFrameDescriptors(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(datPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	// These are decimal LMI1 directory indices. Writing them as 0x83/0x84
	// accidentally selected entries 131/132 (6x7/6x5), not HUD entries 83/84.
	for index, want := range map[int][2]int{83: {44, 12}, 84: {45, 12}, 130: {69, 34}} {
		frame, err := DecodeLMI1FrameResource(datPath, 5, index)
		if err != nil {
			t.Fatalf("entry %#x: %v", index, err)
		}
		if [2]int{frame.Width, frame.Height} != want {
			t.Fatalf("entry %#x geometry=%dx%d, want %dx%d", index, frame.Width, frame.Height, want[0], want[1])
		}
		// 0x1aeb1 directly calls 0x4e63d for entries 83/84. The current
		// generic four-mode decoder does not yet accept their streams, so this
		// test intentionally records descriptor provenance/geometry only. It
		// must not claim a successful GUI/frame decode before that mismatch is
		// independently resolved.
	}
}

func TestParseLMI1FrameEntryRejectsOtherContainerOrIndex(t *testing.T) {
	if _, err := ParseLMI1FrameEntry([]byte("bad"), 0); err == nil {
		t.Fatal("non-LMI1 container was accepted")
	}
	data := make([]byte, 10)
	copy(data, "LMI1")
	binary.LittleEndian.PutUint16(data[4:], 1)
	binary.LittleEndian.PutUint32(data[6:], 10)
	if _, err := ParseLMI1FrameEntry(data, 1); err == nil {
		t.Fatal("out-of-range LMI1 index was accepted")
	}
}

func TestFDOTHER006NativeUnitPresentBank(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(datPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	entries, err := DecodeLMI1Resource(datPath, 6)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 230 {
		t.Fatalf("FDOTHER#6 LMI1 entry count=%d, want 230", len(entries))
	}
	// 0x22470 reads #6 entries 0x72..0x7c; 0x22253's +0x1f6
	// directory pointer is entry 0x7c. These geometry anchors keep the
	// native unit-present resource separate from #81's unused allocation.
	if e := entries[0x72]; e.Width != 12 || e.Height != 21 {
		t.Fatalf("FDOTHER#6 entry#0x72=%dx%d, want 12x21", e.Width, e.Height)
	}
	for index := 0x73; index <= 0x7b; index++ {
		if e := entries[index]; e.Width != 20 || e.Height != 22 {
			t.Fatalf("FDOTHER#6 entry#%#x=%dx%d, want 20x22", index, e.Width, e.Height)
		}
	}
	if e := entries[0x7c]; e.Width != 24 || e.Height != 23 {
		t.Fatalf("FDOTHER#6 entry#0x7c=%dx%d, want 24x23", e.Width, e.Height)
	}
}
