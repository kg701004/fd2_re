// Command fd2-shop-scene-oracle renders the recovered stable target of
// 0x2E341+0x1956B from player-provided original indexed resources. The
// deterministic fixture uses hub variant zero, DATO#129, gold=12345678,
// FDTXT_000 string #440, and service option zero at native pulse phase two.
package main

import (
	"fmt"
	"image"
	"image/color"
	"image/png"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

func main() {
	if len(os.Args) < 5 || len(os.Args) > 8 {
		fmt.Fprintln(os.Stderr, "usage: fd2-shop-scene-oracle FDOTHER.DAT FDTXT.DAT DATO.DAT menu.png [purchase-list.png [purchase-confirm.png [purchase-insufficient.png]]]")
		os.Exit(2)
	}
	fdotherPath, fdtxtPath, datoPath, outputPath := os.Args[1], os.Args[2], os.Args[3], os.Args[4]
	assets, err := campaign.DecodeNativeShopAssets(fdotherPath, 12)
	check(err)
	resource5 := mustResource(fdotherPath, 5)
	dialogue := make([]fdother.RawCell, 18)
	for index := 1; index <= 17; index++ {
		dialogue[index], err = fdother.ParseLMI1RawEntry(resource5, index)
		check(err)
	}
	digits := make([]fdother.Frame, 10)
	for digit := range digits {
		digits[digit], err = fdother.ParseLMI1FrameEntry(resource5, 31+digit)
		check(err)
	}
	portraits, err := dato.DecodeResource(datoPath, 0x81)
	check(err)
	strings, err := fdtxt.Parse(mustResource(fdtxtPath, 0))
	check(err)
	font, err := fdtxt.ParseFont(mustResource(fdotherPath, 4))
	check(err)
	stable, err := campaign.ComposeNativeShopScene(
		assets, dialogue, digits, portraits[0], 0x81,
		strings, font, 12345678, 0x1b8,
	)
	check(err)
	frame, err := campaign.ComposeNativeShopServiceSteadyFrame(stable, assets, 0, 2)
	check(err)
	palette, err := fdother.ParseVGAPalette(mustResource(fdotherPath, 0))
	check(err)
	palette[0] = color.NRGBA{A: 0xff}
	writePNG(outputPath, frame, palette)
	if len(os.Args) >= 6 {
		itemAssets, err := battle.LoadNativeItemPanelDataAssets(fdotherPath, fdtxtPath)
		check(err)
		effectRows, err := battle.LoadNativeItemEffectRowPrefix(
			"assets/data/native_item_effect_rows.json",
		)
		check(err)
		purchase, err := campaign.ComposeNativeShopItemListFrame(
			stable, assets, itemAssets, []int{0, 1, 2, 3, 4, 5},
			0, 0, effectRows, battle.NativeFacilityFullPrice,
		)
		check(err)
		writePNG(os.Args[5], purchase, palette)
	}
	if len(os.Args) >= 7 {
		purchasePortraits, err := dato.DecodeResource(datoPath, 0x80)
		check(err)
		purchaseSource, err := campaign.ComposeNativeShopScene(
			assets, dialogue, digits, purchasePortraits[0], 0x80,
			strings, font, 12345678, 0x1f5,
		)
		check(err)
		choices, err := fdother.DecodeRawCellResource(fdotherPath, 2)
		check(err)
		confirmation, err := campaign.ComposeNativeShopPurchaseConfirmation(
			purchaseSource, dialogue, purchasePortraits[0], 0x80,
			strings, font, choices, campaign.NativeShopPurchaseQuestion,
			1, 0, 50, 0, 1,
		)
		check(err)
		writePNG(os.Args[6], confirmation, palette)
		if len(os.Args) == 8 {
			insufficient, err := campaign.ComposeNativeShopPurchaseInsufficientGold(
				confirmation, strings, font, 1,
			)
			check(err)
			writePNG(os.Args[7], insufficient, palette)
		}
	}
}

func mustResource(path string, index int) []byte {
	resource, err := fdother.ReadResource(path, index)
	check(err)
	return resource
}

func writePNG(path string, pixels []byte, palette color.Palette) {
	out := image.NewPaletted(image.Rect(0, 0, 320, 200), palette)
	copy(out.Pix, pixels)
	file, err := os.Create(path)
	check(err)
	check(png.Encode(file, out))
	check(file.Close())
}

func check(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
