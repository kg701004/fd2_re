package campaign

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

func TestDecodeNativeShopAssetsUsesOriginalMixedCodecResources(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(datPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}

	// 0x2e341 selects exactly these three backgrounds by hub variant.  The
	// outer containers differ, but cell #1 is always the 0x4e8af opaque
	// 63x15 decoration placed at VGA+0x76c5.
	for _, resourceID := range []int{12, 29, 63} {
		assets, err := DecodeNativeShopAssets(datPath, resourceID)
		if err != nil {
			t.Fatalf("FDOTHER#%d: %v", resourceID, err)
		}
		if assets.ResourceID != resourceID || len(assets.Background) != NativeShopWidth*NativeShopHeight {
			t.Fatalf("FDOTHER#%d assets=%+v background=%d", resourceID, assets, len(assets.Background))
		}
		if len(assets.RawEntries) < 11 {
			t.Fatalf("FDOTHER#%d entries=%d, want at least 11", resourceID, len(assets.RawEntries))
		}
		if cell := assets.Decoration; cell.Width != 63 || cell.Height != 15 || len(cell.Pixels) != 63*15 {
			t.Fatalf("FDOTHER#%d cell#1=%dx%d pixels=%d, want 63x15", resourceID, cell.Width, cell.Height, len(cell.Pixels))
		}
	}
}

func TestComposeNativeShopSceneUsesOriginalStableResources(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2"
	fdotherPath := filepath.Join(base, "FDOTHER.DAT")
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided original resources are absent")
	}
	assets, err := DecodeNativeShopAssets(fdotherPath, 12)
	if err != nil {
		t.Fatal(err)
	}
	resource5, err := fdother.ReadResource(fdotherPath, 5)
	if err != nil {
		t.Fatal(err)
	}
	dialogue := make([]fdother.RawCell, 18)
	for index := 1; index <= 17; index++ {
		dialogue[index], err = fdother.ParseLMI1RawEntry(resource5, index)
		if err != nil {
			t.Fatalf("dialogue cell %d: %v", index, err)
		}
	}
	digits := make([]fdother.Frame, 10)
	for digit := range digits {
		digits[digit], err = fdother.ParseLMI1FrameEntry(resource5, 31+digit)
		if err != nil {
			t.Fatalf("digit %d: %v", digit, err)
		}
	}
	portraits, err := dato.DecodeResource(filepath.Join(base, "DATO.DAT"), 0x81)
	if err != nil {
		t.Fatal(err)
	}
	textRaw, err := fdother.ReadResource(filepath.Join(base, "FDTXT.DAT"), 0)
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
	frame, err := ComposeNativeShopScene(
		assets, dialogue, digits, portraits[0], 0x81,
		strings, font, 12345678, 0x1b8,
	)
	if err != nil {
		t.Fatal(err)
	}
	if len(frame) != NativeShopWidth*NativeShopHeight {
		t.Fatalf("frame bytes=%d", len(frame))
	}
	if string(frame) == string(assets.Background) {
		t.Fatal("stable shop overlays did not change the original background")
	}
}

func TestDecodeNativeShopAssetsRejectsUnselectedResource(t *testing.T) {
	if _, err := DecodeNativeShopAssets("irrelevant", 13); err == nil {
		t.Fatal("unselected shop resource was accepted")
	}
}
