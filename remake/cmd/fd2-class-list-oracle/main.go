// Command fd2-class-list-oracle renders the recovered
// 0x311DC+0x31019+0x1974C indexed class-candidate list from player-provided
// original archives. The fixture is 悠妮 (native identity/portrait 9),
// current class 5, special target class 21.
package main

import (
	"fmt"
	"image"
	"image/color"
	"image/png"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

func main() {
	if len(os.Args) != 5 {
		fmt.Fprintln(os.Stderr, "usage: fd2-class-list-oracle FDOTHER.DAT FDTXT.DAT FDICON.B24 output.png")
		os.Exit(2)
	}
	fdotherPath, fdtxtPath, fdiconPath, outputPath := os.Args[1], os.Args[2], os.Args[3], os.Args[4]

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
	units, err := fdicon.DecodeFile(fdiconPath)
	if err != nil {
		fail(err)
	}
	sprite, err := units.SpriteFor(9, 0, 0)
	if err != nil {
		fail(err)
	}
	frame, err := campaign.ComposeNativeClassListFrame(background, entries[16], []campaign.NativeClassListRow{{
		Sprite: sprite, NameTextIndex: 10, CurrentClassTextID: 5, TargetClassTextID: 21,
	}}, 0, strings, font)
	if err != nil {
		fail(err)
	}
	if _, err := campaign.NativeClassListOpeningFrames(background, frame); err != nil {
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
	out := image.NewPaletted(image.Rect(0, 0, 320, 200), palette)
	copy(out.Pix, frame)
	file, err := os.Create(outputPath)
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
