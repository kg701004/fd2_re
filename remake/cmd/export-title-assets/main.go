// export-title-assets 從玩家自備的 FDOTHER.DAT 重新產生 remake/assets/title/
// 底下 title.go 需要的靜態圖檔:立繪捲動大圖、FLAME DRAGON 標題+選單、開場
// 兩張靜態幕。素材/資源號對照見
// docs/knowledge-base/23-boot-title-and-scenario-flow.md §2.1-2.4(已解圖驗證,
// 非本工具新猜測):
//
//   - scroll_big.png: FDOTHER #0x45-0x49(69-73)共 5 幀,各 320×147,直疊成
//     320×735,用 0x4e63d 單幀 RLE(fdother.DecodeArchiveSingleFrame,跟 BG.DAT
//     同格式)。
//   - title.png / menu_1..6.png: FDOTHER #7(巢狀 LLLLLL 容器)sub0-6,用
//     ArchiveEntry+ParseSingleFrame(不是 LMI1);palette=FDOTHER #8(title.go
//     檔頭原本就寫對的號碼)。doc23 §2.1 標的 #0x65 是錯的——那份資源的低位
//     索引(1-7)全部是同一色塊,不是連貫色階;實測 #8 才會重建出玩家提供的
//     真實截圖配色(黑底、火焰橘黃字、藍色「2」),已用真實截圖交叉驗證過,
//     不是本工具新猜測。
//   - cut_guardian.png: image=FDOTHER #100(0x64),palette=FDOTHER #99(0x63)。
//   - cut_castle.png: image=FDOTHER #75(0x4b),palette=FDOTHER #76(0x4c)。
//
// 用法:
//
//	go run ./cmd/export-title-assets <FDOTHER.DAT 路徑> <輸出目錄>
package main

import (
	"fmt"
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: export-title-assets <FDOTHER.DAT path> <out dir>")
		os.Exit(1)
	}
	fdotherPath, outDir := os.Args[1], os.Args[2]
	check(os.MkdirAll(outDir, 0o755))

	mainPalette := loadPalette(fdotherPath, 0)
	titlePalette := loadPalette(fdotherPath, 8)
	guardianPalette := loadPalette(fdotherPath, 0x63)
	castlePalette := loadPalette(fdotherPath, 0x4c)

	exportScroll(fdotherPath, outDir, mainPalette)

	// #7 是巢狀 LLLLLL 容器(doc23 §2.3),不是 LMI1 目錄——sub0-6 各自是
	// ArchiveEntry 取出的獨立 0x4e63d 單幀,跟 scroll 幀同格式。
	resource7, err := fdother.ReadResource(fdotherPath, 7)
	check(err)
	exportNestedFrame(resource7, outDir, "title.png", 0, titlePalette)
	for i := 0; i < 3; i++ {
		exportNestedFrame(resource7, outDir, fmt.Sprintf("menu_%d.png", i*2+1), i*2+1, titlePalette)
		exportNestedFrame(resource7, outDir, fmt.Sprintf("menu_%d.png", i*2+2), i*2+2, titlePalette)
	}
	exportSingleFrame(fdotherPath, outDir, "cut_guardian.png", 0x64, guardianPalette)
	exportSingleFrame(fdotherPath, outDir, "cut_castle.png", 0x4b, castlePalette)

	fmt.Println("done ->", outDir)
}

func loadPalette(fdotherPath string, resource int) color.Palette {
	raw, err := fdother.ReadResource(fdotherPath, resource)
	check(err)
	pal, err := fdother.ParseVGAPalette(raw)
	check(err)
	return pal
}

func exportScroll(fdotherPath, outDir string, pal color.Palette) {
	const frameW, frameH, frames = 320, 147, 5
	dst := make([]byte, frameW*frameH*frames)
	for i := 0; i < frames; i++ {
		f, err := fdother.DecodeArchiveSingleFrame(fdotherPath, 0x45+i)
		check(err)
		if f.Width != frameW || f.Height != frameH {
			fmt.Fprintf(os.Stderr, "scroll frame %d: got %dx%d, want %dx%d\n", i, f.Width, f.Height, frameW, frameH)
		}
		check(f.BlitAt(dst, frameW, i*frameW*frameH, -1))
	}
	writePNG(filepath.Join(outDir, "scroll_big.png"), dst, frameW, frameH*frames, pal)
}

func exportNestedFrame(container []byte, outDir, name string, index int, pal color.Palette) {
	sub, err := fdother.ArchiveEntry(container, index)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s (nested sub %d): %v\n", name, index, err)
		return
	}
	f, err := fdother.ParseSingleFrame(sub)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s (nested sub %d): %v\n", name, index, err)
		return
	}
	dst := make([]byte, f.Width*f.Height)
	check(f.BlitAt(dst, f.Width, 0, -1))
	writePNG(filepath.Join(outDir, name), dst, f.Width, f.Height, pal)
}

func exportSingleFrame(fdotherPath, outDir, name string, resource int, pal color.Palette) {
	f, err := fdother.DecodeArchiveSingleFrame(fdotherPath, resource)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s (resource %d): %v\n", name, resource, err)
		return
	}
	dst := make([]byte, f.Width*f.Height)
	check(f.BlitAt(dst, f.Width, 0, -1))
	writePNG(filepath.Join(outDir, name), dst, f.Width, f.Height, pal)
}

func writePNG(path string, pixels []byte, w, h int, pal color.Palette) {
	out := image.NewPaletted(image.Rect(0, 0, w, h), pal)
	copy(out.Pix, pixels)
	file, err := os.Create(path)
	check(err)
	check(png.Encode(file, out))
	check(file.Close())
	fmt.Printf("  %s (%dx%d)\n", path, w, h)
}

func check(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
