// Command fd2-church-menu-oracle renders the recovered
// 0x3072F+0x2D669+0x2D85F indexed church scene from player-provided original
// resources. The deterministic fixture uses gold=1000, FDTXT585 and option 0.
package main

import (
	"fmt"
	"image"
	"image/color"
	"image/png"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/campaign"
	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

func main() {
	if len(os.Args) != 5 {
		fmt.Fprintln(os.Stderr, "usage: fd2-church-menu-oracle FDOTHER.DAT FDTXT.DAT DATO.DAT output.png")
		os.Exit(2)
	}
	fdotherPath, fdtxtPath, datoPath, outputPath := os.Args[1], os.Args[2], os.Args[3], os.Args[4]
	resource14 := mustResource(fdotherPath, 14)
	entries14, err := fdother.ParseLMI1(resource14)
	check(err)
	backgroundFrame, err := fdother.ParseLMI1FrameEntry(resource14, 0)
	check(err)
	background := make([]byte, 320*200)
	check(backgroundFrame.BlitAt(background, 320, 0, -1))

	resource5 := mustResource(fdotherPath, 5)
	dialogue := make([]fdother.RawCell, 18)
	for index := 1; index <= 17; index++ {
		dialogue[index], err = fdother.ParseLMI1RawEntry(resource5, index)
		check(err)
	}
	digits := make([]fdother.Frame, 10)
	for digit := 0; digit < 10; digit++ {
		digits[digit], err = fdother.ParseLMI1FrameEntry(resource5, 31+digit)
		check(err)
	}
	portraits, err := dato.DecodeResource(datoPath, 131)
	check(err)
	textRaw := mustResource(fdtxtPath, 0)
	strings, err := fdtxt.Parse(textRaw)
	check(err)
	font, err := fdtxt.ParseFont(mustResource(fdotherPath, 4))
	check(err)
	scene, err := campaign.ComposeNativeChurchScene(
		background, entries14[1], dialogue, digits, portraits[0],
		strings, font, 1000, 585,
	)
	check(err)
	frame, err := campaign.ComposeNativeChurchMenuFrame(scene, entries14, 0, 1)
	check(err)
	palette, err := fdother.ParseVGAPalette(mustResource(fdotherPath, 0))
	check(err)
	palette[0] = color.NRGBA{A: 0xff}
	writePNG(outputPath, frame, palette)
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
