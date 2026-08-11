package battle

import "testing"

func TestRenderNativeCommandOverlayMatches1CEEDCoordinates(t *testing.T) {
	assets := nativeItemPanelTestAssets(t, 0)
	book := make([]NativeCommandRecord, 5)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: id + 1}
	}
	dst := make([]byte, nativeItemPanelBytes)
	if err := RenderNativeCommandOverlay(assets, []int{0, 1, 2, 3, 4}, book, nil, 4, dst); err != nil {
		t.Fatal(err)
	}
	// Synthetic glyph 441 starts at index 441 and is drawn at (18,103).
	if got := dst[103*320+18]; got != 205 {
		t.Fatalf("command0 label foreground=%d want 205", got)
	}
	// Fifth command begins the second column at (118,103).
	if got := dst[103*320+118]; got != 201 {
		t.Fatalf("selected command4 foreground=%d want 201", got)
	}
	if got := dst[108*320+68]; got == 0 {
		t.Fatal("command0 MP icon did not render at (68,108)")
	}
}

func TestNativeItemPanelRecordIncludesCommandMaskAt1A(t *testing.T) {
	unit := &Unit{
		BattleFig: 0, NativeIdentity: 0, HasNativeIdentity: true,
		NativeRecordByte6: 1, HasNativeRecordByte6: true,
		NativeRecordRace: 1, HasNativeRecordRace: true,
		NativeRecordClass: 1, HasNativeRecordClass: true,
		Lv: 1, MV: 1,
		InventorySlots:       []int{0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff},
		NativeInventoryFlags: []int{0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80, 0x80},
	}
	unit.NativeCommandMask = [5]byte{1, 2, 3, 4, 5}
	record, err := NativeItemPanelRecordForUnit(unit)
	if err != nil {
		t.Fatal(err)
	}
	for i, want := range unit.NativeCommandMask {
		if got := record[0x1a+i]; got != want {
			t.Fatalf("record command byte%d=%d want %d", i, got, want)
		}
	}
}
