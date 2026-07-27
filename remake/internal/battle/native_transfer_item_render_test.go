package battle

import (
	"encoding/binary"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestRenderNativeTransferItemRowsMatches2DC55Mode1(t *testing.T) {
	assets := nativeItemPanelTestAssets(t, 0)
	rows := make([]byte, 2*NativeItemEffectRowSize)
	rows[0] = 1
	binary.LittleEndian.PutUint16(rows[1:3], 123)
	binary.LittleEndian.PutUint16(rows[19:21], 1000)
	rows[NativeItemEffectRowSize] = 0x15
	binary.LittleEndian.PutUint16(
		rows[NativeItemEffectRowSize+5:NativeItemEffectRowSize+7], 45,
	)
	binary.LittleEndian.PutUint16(
		rows[NativeItemEffectRowSize+19:NativeItemEffectRowSize+21], 200,
	)
	facility := fdother.RawCell{Width: 1, Height: 1, Pixels: []byte{88}}
	dst := make([]byte, nativeItemPanelBytes)
	if err := RenderNativeTransferItemRows(
		assets, facility, []int{0, 1}, 0, 1, rows, dst,
	); err != nil {
		t.Fatal(err)
	}
	if got := dst[119*320+10]; got != 59 {
		t.Fatalf("item0 category=%d want 59", got)
	}
	if got := dst[119*320+158]; got != 60 {
		t.Fatalf("item1 category=%d want 60", got)
	}
	if got := dst[122*320+38]; got != 205 {
		t.Fatalf("item0 label=%d want 205", got)
	}
	if got := dst[122*320+186]; got != 201 {
		t.Fatalf("selected item1 label=%d want 201", got)
	}
	if got := dst[131*320+105]; got != 88 {
		t.Fatalf("facility cell=%d want 88", got)
	}
	// Mode1 displays 3/4 of row+19: 1000 -> 750 with digit base119.
	if got := dst[131*320+114]; got != 119 {
		t.Fatalf("price leading digit=%d want base119", got)
	}
}
