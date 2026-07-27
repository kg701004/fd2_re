// Command fd2-class-list-oracle renders the recovered
// 0x31385 class-change scene from player-provided original archives. The
// fixture is 悠妮 (native identity/portrait 9), current class 5, special
// target class 21.
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
	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

func main() {
	if len(os.Args) != 9 {
		fmt.Fprintln(os.Stderr, "usage: fd2-class-list-oracle FDOTHER.DAT FDTXT.DAT FDICON.B24 DATO.DAT native_item_effect_rows.json list.png confirm.png transfer.png")
		os.Exit(2)
	}
	fdotherPath, fdtxtPath, fdiconPath, datoPath := os.Args[1], os.Args[2], os.Args[3], os.Args[4]
	itemRowsPath := os.Args[5]
	listOutputPath, confirmOutputPath, transferOutputPath := os.Args[6], os.Args[7], os.Args[8]

	resource14, err := fdother.ReadResource(fdotherPath, 14)
	if err != nil {
		fail(err)
	}
	entries, err := fdother.ParseLMI1(resource14)
	if err != nil {
		fail(err)
	}
	backgroundFrame, err := fdother.ParseLMI1FrameEntry(resource14, 0)
	if err != nil {
		fail(err)
	}
	if len(entries) <= 16 || backgroundFrame.Width != 320 || backgroundFrame.Height != 200 {
		fail(fmt.Errorf("FDOTHER#14 lacks native background/panel entries"))
	}
	background := make([]byte, 320*200)
	if err := backgroundFrame.BlitAt(background, 320, 0, -1); err != nil {
		fail(err)
	}
	textRaw, err := fdother.ReadResource(fdtxtPath, 0)
	if err != nil {
		fail(err)
	}
	strings, err := fdtxt.Parse(textRaw)
	if err != nil {
		fail(err)
	}
	fontRaw, err := fdother.ReadResource(fdotherPath, 4)
	if err != nil {
		fail(err)
	}
	font, err := fdtxt.ParseFont(fontRaw)
	if err != nil {
		fail(err)
	}
	resource5, err := fdother.ReadResource(fdotherPath, 5)
	if err != nil {
		fail(err)
	}
	dialogue := make([]fdother.RawCell, 18)
	for index := 1; index <= 17; index++ {
		dialogue[index], err = fdother.ParseLMI1RawEntry(resource5, index)
		if err != nil {
			fail(err)
		}
	}
	digits := make([]fdother.Frame, 10)
	for digit := 0; digit < 10; digit++ {
		digits[digit], err = fdother.ParseLMI1FrameEntry(resource5, 31+digit)
		if err != nil {
			fail(err)
		}
	}
	portraits, err := dato.DecodeResource(datoPath, 131)
	if err != nil || len(portraits) == 0 {
		if err != nil {
			fail(err)
		}
		fail(fmt.Errorf("DATO#131 has no frames"))
	}
	scene, err := campaign.ComposeNativeChurchScene(
		background, entries[1], dialogue, digits, portraits[0], strings, font, 1000, 585,
	)
	if err != nil {
		fail(err)
	}
	source, err := campaign.NativeChurchMenuBase(scene)
	if err != nil {
		fail(err)
	}
	units, err := fdicon.DecodeFile(fdiconPath)
	if err != nil {
		fail(err)
	}
	sprite, err := units.SpriteFor(9, 0, 0)
	if err != nil {
		fail(err)
	}
	frame, err := campaign.ComposeNativeClassListFrame(source, entries[16], []campaign.NativeClassListRow{{
		Sprite: sprite, NameTextIndex: 10, CurrentClassTextID: 5, TargetClassTextID: 21,
	}}, 0, strings, font)
	if err != nil {
		fail(err)
	}
	if _, err := campaign.NativeClassListOpeningFrames(source, frame); err != nil {
		fail(err)
	}
	if _, err := campaign.NativeClassListClosingFrames(source, frame); err != nil {
		fail(err)
	}
	cells, err := fdother.DecodeRawCellResource(fdotherPath, 2)
	if err != nil {
		fail(err)
	}
	dialogueBase, err := campaign.ComposeNativeChurchDialogueOverlay(source, dialogue, portraits[0])
	if err != nil {
		fail(err)
	}
	confirm, err := campaign.ComposeNativeClassConfirmationFrame(dialogueBase, cells, strings, font, 10, 0, 1)
	if err != nil {
		fail(err)
	}
	if _, err := campaign.NativeClassConfirmationOpeningFrames(confirm, cells); err != nil {
		fail(err)
	}
	if _, err := campaign.NativeClassConfirmationClosingFrames(confirm, cells); err != nil {
		fail(err)
	}
	if _, err := campaign.NativeClassListClosingFrames(source, dialogueBase); err != nil {
		fail(err)
	}
	transfer := append([]byte(nil), source...)
	if err := entries[16].BlitOpaqueAt(transfer, 320, 5, 112, false); err != nil {
		fail(err)
	}
	itemAssets, err := battle.LoadNativeItemPanelDataAssets(fdotherPath, fdtxtPath)
	if err != nil {
		fail(err)
	}
	itemRows, err := battle.LoadNativeItemEffectRowPrefix(itemRowsPath)
	if err != nil {
		fail(err)
	}
	priceCell, err := fdother.ParseLMI1RawEntry(resource14, 15)
	if err != nil {
		fail(err)
	}
	if err := battle.RenderNativeTransferItemRows(
		itemAssets, priceCell, []int{0, 79, 90}, 0, 1, itemRows, transfer,
	); err != nil {
		fail(err)
	}
	paletteRaw, err := fdother.ReadResource(fdotherPath, 0)
	if err != nil {
		fail(err)
	}
	palette, err := fdother.ParseVGAPalette(paletteRaw)
	if err != nil {
		fail(err)
	}
	palette[0] = color.NRGBA{A: 0xff}
	writePNG(listOutputPath, frame, palette)
	writePNG(confirmOutputPath, confirm, palette)
	writePNG(transferOutputPath, transfer, palette)
}

func writePNG(path string, pixels []byte, palette color.Palette) {
	out := image.NewPaletted(image.Rect(0, 0, 320, 200), palette)
	copy(out.Pix, pixels)
	file, err := os.Create(path)
	if err != nil {
		fail(err)
	}
	if err := png.Encode(file, out); err != nil {
		file.Close()
		fail(err)
	}
	if err := file.Close(); err != nil {
		fail(err)
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
