// export-ring-icons extracts the 4 battle action-menu icons (attack/spell/
// item/wait) from a player-provided original FDOTHER.DAT, so the classic
// (non-native) renderer's radial action menu can show the real original art
// instead of a text-label fallback.
//
// These are FDOTHER resource #2's raw indexed cells. internal/fdother/
// action_overlay.go's CellIndex documents the exact selection formula used
// by the native battle action wrapper (0x18d8c): index = 3*availability +
// 2*directionState, with BattleActionOverlayState's fixed DirectionState =
// [0,1,2,3] for the four directions (up/left/right/down = attack/spell/
// item/wait, per the ring's own navigation convention, doc13 [0x3C57]) and
// availability=0 meaning ENABLED (counterintuitive but confirmed by the
// existing "enabled action selects cells [0,2,4,6]" comment on that
// function). So the enabled-state icon for each direction is cell
// 3*0+2*directionState = 2*directionState: 0, 2, 4, 6.
//
// Usage:
//
//	go run ./cmd/export-ring-icons <FDOTHER.DAT path> <output dir>
package main

import (
	"fmt"
	"image/png"
	"os"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: export-ring-icons <FDOTHER.DAT path> <output dir>")
		os.Exit(1)
	}
	datPath, outDir := os.Args[1], os.Args[2]

	paletteRaw, err := fdother.ReadResource(datPath, 0)
	check(err)
	palette, err := fdother.ParseVGAPalette(paletteRaw)
	check(err)

	cells, err := fdother.DecodeRawCellResource(datPath, 2)
	check(err)
	if len(cells) < 10 {
		fmt.Fprintf(os.Stderr, "expected >=10 raw cells in FDOTHER resource 2, got %d\n", len(cells))
		os.Exit(1)
	}

	// 2026-08-14: the cell storage order is NOT the same as the ring's own
	// gameplay slot order. The gameplay direction/slot pairing (0=attack/
	// 1=spell/2=item/3=wait, up/left/right/down) is disassembly-confirmed at
	// native 0x18d8c's switch and must never be touched here. But cross-
	// checking a fresh extraction (against the now-correct reference-version
	// FDOTHER.DAT, see docs/data/fd2-reference-files.json) against the
	// player's own memory of the real game showed the RESOURCE's 4 cells are
	// stored in a different order: cell0=attack, cell2=rest/wait, cell4=
	// spell/magic, cell6=item. This mapping is player-confirmed, not derived
	// from CellIndex's directionState assumption (which was wrong). See
	// docs/knowledge-base/58-remake-live-verification-log.md Bug 5.
	names := []string{"attack", "wait", "status", "item"}
	indices := []int{0, 2, 4, 6}

	check(os.MkdirAll(outDir, 0o755))
	for i, idx := range indices {
		im, err := cells[idx].Paletted(palette)
		check(err)
		outPath := fmt.Sprintf("%s/ring_%s.png", outDir, names[i])
		f, err := os.Create(outPath)
		check(err)
		check(png.Encode(f, im))
		check(f.Close())
		b := im.Bounds()
		fmt.Printf("%s: cell %d, %dx%d\n", outPath, idx, b.Dx(), b.Dy())
	}
}

func check(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
