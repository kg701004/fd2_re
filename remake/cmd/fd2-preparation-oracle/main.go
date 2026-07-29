// Command fd2-preparation-oracle renders the evidence-closed subpasses of the
// original 0x318ad preparation roster. It is a resource/compositor oracle, not
// an original runtime capture or a fabricated FD2.SAV.
package main

import (
	"flag"
	"fmt"
	"image"
	"image/png"
	"os"
	"path/filepath"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func main() {
	base := flag.String("base", "", "player-owned FLAME2 directory")
	scenario := flag.String("scenario", "", "editable scenario supplying one proven native party record")
	out := flag.String("out", "preparation-roster-oracle.png", "output PNG")
	flag.Parse()
	if *base == "" {
		fmt.Fprintln(os.Stderr, "缺少 -base：請指定玩家持有的 FLAME2 目錄")
		os.Exit(2)
	}
	fdotherPath := filepath.Join(*base, "FDOTHER.DAT")
	assets, err := fdother.DecodeNativePreparationAssets(
		fdotherPath, filepath.Join(*base, "FDICON.B24"),
	)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	keys := make([]int, 20)
	selected := make([]bool, len(keys))
	for i := range keys {
		keys[i] = i
		selected[i] = i < 5
	}
	frame, err := fdother.ComposeNativePreparationFrame(
		assets, keys, selected, 0, 0, 15,
	)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if *scenario != "" {
		dataAssets, err := battle.LoadNativeItemPanelDataAssets(
			fdotherPath, filepath.Join(*base, "FDTXT.DAT"),
		)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		battleScenario, err := battle.LoadScenario(*scenario)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		units := battleScenario.PartyUnits(nil)
		if len(units) == 0 {
			fmt.Fprintln(os.Stderr, "指定情境沒有可用的原始玩家角色記錄")
			os.Exit(1)
		}
		record, err := battle.NativeItemPanelRecordForUnit(units[0])
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		if err := battle.RenderNativeItemPanelData(dataAssets, record, frame); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	paletteRaw, err := fdother.ReadResource(fdotherPath, 0)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	palette, err := fdother.ParseVGAPalette(paletteRaw)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	indexed := image.NewPaletted(image.Rect(0, 0, 320, 200), palette)
	copy(indexed.Pix, frame)
	scaled := image.NewPaletted(image.Rect(0, 0, 640, 400), palette)
	for y := 0; y < 400; y++ {
		for x := 0; x < 640; x++ {
			scaled.SetColorIndex(x, y, indexed.ColorIndexAt(x/2, y/2))
		}
	}
	file, err := os.Create(*out)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer file.Close()
	if err := png.Encode(file, scaled); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
