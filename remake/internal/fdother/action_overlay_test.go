package fdother

import "testing"

func TestActionOverlayCellIndex(t *testing.T) {
	state := ActionOverlayState{
		Availability:   [4]int{0, 1, 0, 1},
		DirectionState: [4]int{0x12, 0x14, 0x16, 0x18},
	}
	want := [4]int{36, 43, 44, 51}
	for direction := range want {
		got, err := state.CellIndex(direction)
		if err != nil || got != want[direction] {
			t.Fatalf("direction %d: index=%d err=%v, want %d", direction, got, err, want[direction])
		}
	}
	if _, err := state.CellIndex(4); err == nil {
		t.Fatal("invalid direction was accepted")
	}
}

func TestActionOverlayOriginMatchesNativeAddressExpression(t *testing.T) {
	got, err := ActionOverlayOrigin(6, 5)
	if err != nil {
		t.Fatal(err)
	}
	want := 0x8088 + 6*0x18 + 5*0x18*0x1c8
	if got != want {
		t.Fatalf("origin=%#x, want %#x", got, want)
	}
	if _, err := ActionOverlayOrigin(-1, 0); err == nil {
		t.Fatal("negative origin was accepted")
	}
}

func TestActionOverlayFrameOffsets(t *testing.T) {
	got, err := ActionOverlayFrameOffsets(1, false)
	if err != nil {
		t.Fatal(err)
	}
	want := [4]int{0x390 - 0x8e8, 0x390 - 6, 0x390 + 6, 0x390 + 0x8e8}
	if got != want {
		t.Fatalf("opening offsets=%#x, want %#x", got, want)
	}
	got, err = ActionOverlayFrameOffsets(0, true)
	if err != nil {
		t.Fatal(err)
	}
	if got != [4]int{-0x23a0, 0x378, 0x3a8, 0x2ac0} {
		t.Fatalf("closing offsets=%#x", got)
	}
	if _, err := ActionOverlayFrameOffsets(4, false); err == nil {
		t.Fatal("invalid frame was accepted")
	}
}

func TestBlitActionOverlayFrameUsesNativeCellsAndTransparency(t *testing.T) {
	cells := make([]RawCell, 52)
	for i := range cells {
		cells[i] = RawCell{Width: 1, Height: 1, Pixels: []byte{byte(i + 1)}}
	}
	// Direction 1 intentionally has a transparent pixel, which must preserve dst.
	cells[43].Pixels[0] = 0
	state := ActionOverlayState{
		Availability:   [4]int{0, 1, 0, 1},
		DirectionState: [4]int{0x12, 0x14, 0x16, 0x18},
	}
	const stride = 500
	dst := make([]byte, stride*20)
	for i := range dst {
		dst[i] = 0xee
	}
	const origin = stride*10 + 100
	if err := BlitActionOverlayFrame(cells, state, dst, stride, origin, 1, false); err != nil {
		t.Fatal(err)
	}
	offsets, _ := ActionOverlayFrameOffsets(1, false)
	if got := dst[origin+offsets[0]]; got != 37 { // cell 36
		t.Fatalf("up pixel=%d, want 37", got)
	}
	if got := dst[origin+offsets[1]]; got != 0xee { // transparent cell 43
		t.Fatalf("left transparent pixel=%d, want preserved", got)
	}
	if got := dst[origin+offsets[2]]; got != 45 { // cell 44
		t.Fatalf("right pixel=%d, want 45", got)
	}
	if got := dst[origin+offsets[3]]; got != 52 { // cell 51
		t.Fatalf("down pixel=%d, want 52", got)
	}
}
