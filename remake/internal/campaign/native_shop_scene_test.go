package campaign

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
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
	stableBefore := append([]byte(nil), frame...)
	for step := 0; step < 4; step++ {
		opening, err := ComposeNativeShopServiceOpeningFrame(frame, assets, step)
		if err != nil {
			t.Fatalf("service opening step %d: %v", step, err)
		}
		if len(opening) != NativeShopWidth*NativeShopHeight ||
			string(opening) == string(frame) {
			t.Fatalf("service opening step %d did not render", step)
		}
	}
	normal, err := ComposeNativeShopServiceSteadyFrame(frame, assets, 0, 0)
	if err != nil {
		t.Fatal(err)
	}
	selected, err := ComposeNativeShopServiceSteadyFrame(frame, assets, 0, 2)
	if err != nil {
		t.Fatal(err)
	}
	if string(normal) == string(selected) {
		t.Fatal("selected service pulse variant did not change the frame")
	}
	if string(frame) != string(stableBefore) {
		t.Fatal("service compositors mutated the caller-owned stable frame")
	}
	itemAssets, err := battle.LoadNativeItemPanelDataAssets(
		fdotherPath, filepath.Join(base, "FDTXT.DAT"),
	)
	if err != nil {
		t.Fatal(err)
	}
	effectRows, err := battle.LoadNativeItemEffectRowPrefix(
		"../../assets/data/native_item_effect_rows.json",
	)
	if err != nil {
		t.Fatal(err)
	}
	purchase, err := ComposeNativeShopItemListFrame(
		frame, assets, itemAssets, []int{0, 1}, 0, 1, effectRows,
		battle.NativeFacilityFullPrice,
	)
	if err != nil {
		t.Fatal(err)
	}
	sale, err := ComposeNativeShopItemListFrame(
		frame, assets, itemAssets, []int{0, 1}, 0, 1, effectRows,
		battle.NativeFacilityThreeQuarterPrice,
	)
	if err != nil {
		t.Fatal(err)
	}
	if string(purchase) == string(sale) {
		t.Fatal("purchase and sale price modes rendered the same child panel")
	}
	if string(frame) != string(stableBefore) {
		t.Fatal("child-panel compositor mutated the stable shop frame")
	}
	purchasePortraits, err := dato.DecodeResource(
		filepath.Join(base, "DATO.DAT"), 0x80,
	)
	if err != nil {
		t.Fatal(err)
	}
	purchaseSource, err := ComposeNativeShopScene(
		assets, dialogue, digits, purchasePortraits[0], 0x80,
		strings, font, 12345678, 0x1f5,
	)
	if err != nil {
		t.Fatal(err)
	}
	choices, err := fdother.DecodeRawCellResource(fdotherPath, 2)
	if err != nil {
		t.Fatal(err)
	}
	for _, message := range []NativeShopPurchaseMessage{
		NativeShopPurchaseQuestion,
		NativeShopPurchaseNoEligibleRecipient,
		NativeShopPurchaseEquipQuestion,
	} {
		messageFrame, err := ComposeNativeShopPurchaseMessage(
			purchaseSource, dialogue, purchasePortraits[0], 0x80,
			strings, font, message, 1, 0, 50,
		)
		if err != nil {
			t.Fatalf("purchase message %d: %v", message, err)
		}
		if len(messageFrame) != NativeShopWidth*NativeShopHeight {
			t.Fatalf("purchase message %d bytes=%d", message, len(messageFrame))
		}
	}
	confirmation, err := ComposeNativeShopPurchaseConfirmation(
		purchaseSource, dialogue, purchasePortraits[0], 0x80,
		strings, font, choices, NativeShopPurchaseQuestion,
		1, 0, 50, 0, 1,
	)
	if err != nil {
		t.Fatal(err)
	}
	if string(confirmation) == string(purchaseSource) {
		t.Fatal("purchase confirmation did not change the source frame")
	}
	confirmationBefore := append([]byte(nil), confirmation...)
	insufficient, err := ComposeNativeShopPurchaseInsufficientGold(
		confirmation, strings, font, 1,
	)
	if err != nil {
		t.Fatal(err)
	}
	if string(insufficient) == string(confirmationBefore) {
		t.Fatal("insufficient-gold feedback did not append to confirmation")
	}
	if string(insufficient[:157*NativeShopWidth+12]) !=
		string(confirmationBefore[:157*NativeShopWidth+12]) {
		t.Fatal("insufficient-gold feedback changed pixels before literal VGA target")
	}
	if _, err := ComposeNativeShopPurchaseMessage(
		purchaseSource, dialogue, purchasePortraits[0], 0x80,
		strings, font, NativeShopPurchaseInsufficientGold, 1, 0, 50,
	); err == nil {
		t.Fatal("insufficient-gold feedback accepted a fresh dialogue source")
	}
}

func TestNativeShopPurchaseTextTablesPreserveSixVariants(t *testing.T) {
	want := [4][6]int{
		{1, 502, 1, 439, 1, 439},
		{1, 504, 1, 438, 1, 438},
		{1, 505, 1, 437, 1, 437},
		{1, 507, 1, 507, 1, 507},
	}
	for message := NativeShopPurchaseQuestion; message <= NativeShopPurchaseEquipQuestion; message++ {
		for variant := 0; variant < 6; variant++ {
			got, ok := NativeShopPurchaseTextIndex(message, variant)
			if !ok || got != want[message][variant] {
				t.Fatalf("message=%d variant=%d: %d,%v", message, variant, got, ok)
			}
		}
	}
	if _, ok := NativeShopPurchaseTextIndex(NativeShopPurchaseMessage(4), 0); ok {
		t.Fatal("unknown purchase message was accepted")
	}
}

func TestComposeNativeShopServiceMenuRejectsInvalidState(t *testing.T) {
	stable := make([]byte, NativeShopWidth*NativeShopHeight)
	assets := &NativeShopAssets{}
	for _, call := range []func() error{
		func() error {
			_, err := ComposeNativeShopServiceOpeningFrame(stable, assets, -1)
			return err
		},
		func() error {
			_, err := ComposeNativeShopServiceSteadyFrame(stable, assets, 4, 0)
			return err
		},
		func() error {
			_, err := ComposeNativeShopServiceSteadyFrame(stable, assets, 0, 4)
			return err
		},
	} {
		if err := call(); err == nil {
			t.Fatal("invalid native service-menu state was accepted")
		}
	}
}

func TestDecodeNativeShopAssetsRejectsUnselectedResource(t *testing.T) {
	if _, err := DecodeNativeShopAssets("irrelevant", 13); err == nil {
		t.Fatal("unselected shop resource was accepted")
	}
}
