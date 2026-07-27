package battle

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestRenderNativeReviveRowsMatches30A47Geometry(t *testing.T) {
	assets := nativeItemPanelTestAssets(t, 0)
	sprite := fdicon.Sprite{
		Pixels: make([]byte, fdicon.NativeSize*fdicon.NativeSize),
		Mask:   make([]byte, fdicon.NativeSize*fdicon.NativeSize),
	}
	sprite.Pixels[0], sprite.Mask[0] = 99, 1
	currency := fdother.RawCell{Width: 1, Height: 1, Pixels: []byte{88}}
	rows := []NativeReviveRow{
		{Sprite: sprite, NameTextIndex: 1, RaceTextIndex: 140, ClassTextIndex: 150, Fee: 28},
		{Sprite: sprite, NameTextIndex: 1, RaceTextIndex: 140, ClassTextIndex: 150, Fee: 321},
	}
	dst := make([]byte, nativeItemPanelBytes)
	if err := RenderNativeReviveRows(assets, currency, rows, 1, dst); err != nil {
		t.Fatal(err)
	}
	if got := dst[117*320+14]; got != 99 {
		t.Fatalf("row0 sprite=%d want 99", got)
	}
	if got := dst[143*320+14]; got != 99 {
		t.Fatalf("row1 sprite=%d want 99", got)
	}
	if got := dst[121*320+40]; got != 205 {
		t.Fatalf("row0 name=%d want 205", got)
	}
	if got := dst[147*320+40]; got != 201 {
		t.Fatalf("selected row1 name=%d want 201", got)
	}
	if got := dst[125*320+220]; got != 88 {
		t.Fatalf("currency=%d want 88", got)
	}
	if got := dst[125*320+228]; got != 119 {
		t.Fatalf("fee leading digit=%d want base119", got)
	}
}
