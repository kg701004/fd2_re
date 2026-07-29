package campaign

import (
	"image"
	_ "image/png"
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

func loadNativeLoadSlotTestAssets(t *testing.T) (
	fdother.LMI1Entry,
	*fdtxt.Strings,
	*fdtxt.Font,
) {
	t.Helper()
	base := filepath.Join("..", "..", "..")
	fdotherPath := filepath.Join(base, "org_game", "炎龍騎士團", "FLAME2", "FDOTHER.DAT")
	resource13, err := fdother.ReadResource(fdotherPath, 13)
	if err != nil {
		t.Fatal(err)
	}
	entries, err := fdother.ParseLMI1(resource13)
	if err != nil || len(entries) <= 16 {
		t.Fatal(err)
	}
	textRaw, err := fdother.ReadResource(
		filepath.Join(filepath.Dir(fdotherPath), "FDTXT.DAT"), 0,
	)
	if err != nil {
		t.Fatal(err)
	}
	strings, err := fdtxt.Parse(textRaw)
	if err != nil {
		t.Fatal(err)
	}
	fontRaw, err := fdother.ReadResource(fdotherPath, 4)
	if err != nil {
		t.Fatal(err)
	}
	font, err := fdtxt.ParseFont(fontRaw)
	if err != nil {
		t.Fatal(err)
	}
	return entries[16], strings, font
}

func TestComposeNativeLoadSlotsFrameMatchesEmptyDOSBoxOracle(t *testing.T) {
	dialogueBox, strings, font := loadNativeLoadSlotTestAssets(t)
	frame, err := ComposeNativeLoadSlotsFrame(
		make([]byte, NativeLoadSlotWidth*NativeLoadSlotHeight),
		dialogueBox, strings, font,
		[4]NativeLoadSlot{
			{Empty: true},
			{Empty: true},
			{Empty: true},
			{Empty: true},
		},
		0,
	)
	if err != nil {
		t.Fatal(err)
	}
	base := filepath.Join("..", "..", "..")
	paletteRaw, err := fdother.ReadResource(
		filepath.Join(base, "org_game", "炎龍騎士團", "FLAME2", "FDOTHER.DAT"),
		0,
	)
	if err != nil {
		t.Fatal(err)
	}
	palette, err := fdother.ParseVGAPalette(paletteRaw)
	if err != nil {
		t.Fatal(err)
	}
	oracleFile, err := os.Open(filepath.Join(
		base, "docs", "figures", "load-empty-original-dosbox.png",
	))
	if err != nil {
		t.Fatal(err)
	}
	defer oracleFile.Close()
	oracle, _, err := image.Decode(oracleFile)
	if err != nil {
		t.Fatal(err)
	}
	if oracle.Bounds().Dx() != NativeLoadSlotWidth ||
		oracle.Bounds().Dy() != NativeLoadSlotHeight {
		t.Fatalf("oracle bounds=%v", oracle.Bounds())
	}
	mismatches := 0
	firstX, firstY := -1, -1
	lastX, lastY := -1, -1
	var firstGot, firstWant [3]uint32
	for y := 0; y < NativeLoadSlotHeight; y++ {
		for x := 0; x < NativeLoadSlotWidth; x++ {
			got := palette[frame[y*NativeLoadSlotWidth+x]]
			want := oracle.At(oracle.Bounds().Min.X+x, oracle.Bounds().Min.Y+y)
			gr, gg, gb, _ := got.RGBA()
			wr, wg, wb, _ := want.RGBA()
			if gr != wr || gg != wg || gb != wb {
				mismatches++
				lastX, lastY = x, y
				if firstX < 0 {
					firstX, firstY = x, y
					firstGot = [3]uint32{gr >> 8, gg >> 8, gb >> 8}
					firstWant = [3]uint32{wr >> 8, wg >> 8, wb >> 8}
				}
			}
		}
	}
	if mismatches != 0 {
		t.Fatalf(
			"RGB mismatches=%d; bounds=(%d,%d)..(%d,%d); first got=%v want=%v",
			mismatches, firstX, firstY, lastX, lastY, firstGot, firstWant,
		)
	}
}

func TestComposeNativeLoadSlotsFrameRejectsInvalidState(t *testing.T) {
	dialogueBox, strings, font := loadNativeLoadSlotTestAssets(t)
	if _, err := ComposeNativeLoadSlotsFrame(
		make([]byte, NativeLoadSlotWidth*NativeLoadSlotHeight),
		dialogueBox, strings, font, [4]NativeLoadSlot{}, 4,
	); err == nil {
		t.Fatal("invalid selection accepted")
	}
}
