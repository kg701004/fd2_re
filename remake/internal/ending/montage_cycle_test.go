package ending

import (
	"os"
	"testing"
)

func montageCyclePlayerPaths() MontageArchivePaths {
	const base = "../../../org_game/炎龍騎士團/FLAME2/"
	return MontageArchivePaths{
		FDOTHER: base + "FDOTHER.DAT",
		TAI:     base + "TAI.DAT",
		FIGANI:  base + "FIGANI.DAT",
		DATO:    base + "DATO.DAT",
		FDTXT:   base + "FDTXT.DAT",
	}
}

func montageCycleUnits() [][]byte {
	units := make([][]byte, 2)
	for i := range units {
		units[i] = make([]byte, 0x21)
		units[i][6] = byte(i) // exercise both native 0x29164 branches
		units[i][7] = 4       // player-provided FIGANI/DATO group
		units[i][8] = 4       // permanent FDTXT character index source
		units[i][0x20] = 2    // permanent FDTXT class index source
	}
	return units
}

func TestLoadMontageCycleAssetsUsesOnlyProvenanceBoundPlayerResources(t *testing.T) {
	paths := montageCyclePlayerPaths()
	for _, path := range []string{paths.FDOTHER, paths.TAI, paths.FIGANI, paths.DATO, paths.FDTXT} {
		if _, err := os.Stat(path); err != nil {
			t.Skip("player-provided original archives are absent")
		}
	}
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	assets, err := LoadMontageCycleAssets(*montage, paths, montageCycleUnits())
	if err != nil {
		t.Fatal(err)
	}
	if assets.Backdrop.Width != Width || assets.Backdrop.Height != Height || len(assets.Grid) != Bytes || len(assets.TAI003) == 0 {
		t.Fatalf("assets geometry=%dx%d grid=%d tai=%d", assets.Backdrop.Width, assets.Backdrop.Height, len(assets.Grid), len(assets.TAI003))
	}
	if assets.Primary[13] == nil || assets.Secondary[12] == nil || len(assets.Portraits[4]) != 4 {
		t.Fatalf("missing group 4 FIGANI/DATO assets: primary=%v secondary=%v portraits=%d", assets.Primary[13] != nil, assets.Secondary[12] != nil, len(assets.Portraits[4]))
	}
}

func TestMontageCycleExecutesBothNativeSideBranchesAndFinalPaletteFade(t *testing.T) {
	paths := montageCyclePlayerPaths()
	for _, path := range []string{paths.FDOTHER, paths.TAI, paths.FIGANI, paths.DATO, paths.FDTXT} {
		if _, err := os.Stat(path); err != nil {
			t.Skip("player-provided original archives are absent")
		}
	}
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	units := montageCycleUnits()
	assets, err := LoadMontageCycleAssets(*montage, paths, units)
	if err != nil {
		t.Fatal(err)
	}
	c := NewIndexedCompositor()
	if err := c.PresentANI(make([]byte, Bytes), make([]byte, len(c.Palette))); err != nil {
		t.Fatal(err)
	}
	cycle, err := NewMontageCycle(*montage, assets, units, []byte{4, 4}, c)
	if err != nil {
		t.Fatal(err)
	}
	steps := 0
	for !cycle.Ready() && steps < 2000 {
		if err := cycle.Step(byte(steps * 17)); err != nil {
			t.Fatalf("step %d phase=%s: %v", steps, cycle.Phase, err)
		}
		steps++
	}
	if !cycle.Ready() {
		t.Fatalf("native cycle did not complete after %d steps; phase=%s plan=%d", steps, cycle.Phase, cycle.PlanIndex)
	}
	if cycle.PlanIndex != 2 || cycle.FadeOut != 64 {
		t.Fatalf("completed cycle state=%#v", cycle)
	}
}
