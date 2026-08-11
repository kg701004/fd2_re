package indexedmap

import (
	"bytes"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func spawnIntroTestInput(t *testing.T) NativeSpawnIntroFrameInput {
	t.Helper()
	cache := &fdicon.NativeSelectorCache{}
	if _, err := cache.SlotFor(0); err != nil {
		t.Fatal(err)
	}
	cells := make([]fdicon.NativeTerrainCell, 13*8)
	for i := range cells {
		cells[i].BlitMode = 0xff
	}
	identity := make([]byte, 256)
	for i := range identity {
		identity[i] = byte(i)
	}
	unitBank := bank(12, 0)
	pixels, mask := make([]byte, fdicon.NativeSize*fdicon.NativeSize), make([]byte, fdicon.NativeSize*fdicon.NativeSize)
	pixels[0], mask[0] = 3, 1
	unitBank.Sprites[0] = fdicon.Sprite{Pixels: pixels, Mask: mask, RemapMask: make([]byte, len(pixels))}
	return NativeSpawnIntroFrameInput{
		OldUnitCount: 1,
		Frame: NativeTransitionFrameInput{
			TerrainBank: bank(12, 1), UnitBank: unitBank, ForegroundBank: bank(12, 0),
			SelectorCache: cache, Cells: cells, Controls: []byte{0, 0, 0, 0}, TerrainLUT: identity,
			MapWidth: 13,
			Units: []fdicon.NativeUnitLayerEntry{
				{X: 0, Y: 0, Slot: 0},
				{X: 1, Y: 1, Slot: 0},
			},
			ForegroundUnits: []fdicon.NativeForegroundLayerEntry{
				{Inactive: true}, {Inactive: true},
			},
		},
	}
}

func TestComposeNativeSpawnIntroOrdinaryPassPresentsLMIAndKeepsSnapshot(t *testing.T) {
	in := spawnIntroTestInput(t)
	work := make([]byte, NativeUnitPresentWorkSize)
	vga := make([]byte, NativeMapVGASize)
	snapshot := make([]byte, NativeUnitPresentWorkSize)
	for i := range snapshot {
		snapshot[i] = 1
	}
	before := append([]byte(nil), snapshot...)
	entry := fdother.LMI1Entry{Width: 1, Height: 1, Pixels: []byte{0x44}}
	step := fdother.NativeSpawnIntroSchedule()[0]
	if err := ComposeNativeSpawnIntroPass(work, vga, snapshot, in, entry, step); err != nil {
		t.Fatal(err)
	}
	origin := fdother.NativeSpawnIntroLMIOrigin(1, 1, 0, 0)
	relative := origin - workBase
	vgaOffset := relative/workStride*viewWidth + relative%workStride
	if vga[vgaOffset] != 0x44 || work[origin] != 0x44 {
		t.Fatalf("ordinary pass LMI work/vga=%#x/%#x", work[origin], vga[vgaOffset])
	}
	if !bytes.Equal(snapshot, before) {
		t.Fatal("ordinary pass changed persistent snapshot")
	}
}

func TestComposeNativeSpawnIntroPass6RebuildsOldAndLiftedNewUnitsAfterPresent(t *testing.T) {
	in := spawnIntroTestInput(t)
	work := make([]byte, NativeUnitPresentWorkSize)
	vga := make([]byte, NativeMapVGASize)
	snapshot := make([]byte, NativeUnitPresentWorkSize)
	entry := fdother.LMI1Entry{Width: 1, Height: 1, Pixels: []byte{0x44}}
	step := fdother.NativeSpawnIntroSchedule()[6]
	if err := ComposeNativeSpawnIntroPass(work, vga, snapshot, in, entry, step); err != nil {
		t.Fatal(err)
	}
	oldOffset, _ := fdicon.NativePlacementOffset(0x8088, fdicon.NativeMapStride, 0, 0, 0, 0, 0, 0, 0, false)
	newOffset, _ := fdicon.NativePlacementOffset(0x8088, fdicon.NativeMapStride, 1, 1, 0, 0, 0, 0, 0, false)
	lifted := newOffset - 8*workStride
	if snapshot[oldOffset] != 3 || snapshot[lifted] != 3 || snapshot[newOffset] != 0 {
		t.Fatalf("pass6 snapshot old/lifted/normal=%d/%d/%d", snapshot[oldOffset], snapshot[lifted], snapshot[newOffset])
	}
	if !bytes.Equal(work, snapshot) {
		t.Fatal("pass6 work did not advance to rebuilt snapshot")
	}
	origin := fdother.NativeSpawnIntroLMIOrigin(1, 1, 0, 0)
	relative := origin - workBase
	vgaOffset := relative/workStride*viewWidth + relative%workStride
	if vga[vgaOffset] != 0x44 {
		t.Fatalf("pass6 presented post-rebuild state instead of LMI frame: %#x", vga[vgaOffset])
	}
}

func TestComposeNativeSpawnIntroRejectsBadBoundaryAtomically(t *testing.T) {
	in := spawnIntroTestInput(t)
	in.OldUnitCount = 3
	work := make([]byte, NativeUnitPresentWorkSize)
	vga := make([]byte, NativeMapVGASize)
	snapshot := make([]byte, NativeUnitPresentWorkSize)
	work[0], vga[0], snapshot[0] = 1, 2, 3
	if err := ComposeNativeSpawnIntroPass(
		work, vga, snapshot, in,
		fdother.LMI1Entry{Width: 1, Height: 1, Pixels: []byte{4}},
		fdother.NativeSpawnIntroSchedule()[0],
	); err == nil {
		t.Fatal("invalid old/new roster boundary accepted")
	}
	if work[0] != 1 || vga[0] != 2 || snapshot[0] != 3 {
		t.Fatal("rejected spawn-intro pass mutated caller buffers")
	}
}

func TestSeedNativeSpawnIntroSnapshotRequiresFullWorkBuffer(t *testing.T) {
	work := make([]byte, NativeUnitPresentWorkSize)
	work[0] = 7
	snapshot, err := SeedNativeSpawnIntroSnapshot(work)
	if err != nil {
		t.Fatal(err)
	}
	work[0] = 8
	if snapshot[0] != 7 {
		t.Fatal("snapshot aliases mutable work buffer")
	}
	if _, err := SeedNativeSpawnIntroSnapshot(work[:10]); err == nil {
		t.Fatal("short snapshot seed accepted")
	}
}
