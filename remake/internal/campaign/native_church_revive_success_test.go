package campaign

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestPlanNativeChurchReviveSuccessPreservesCase4Schedule(t *testing.T) {
	plan := PlanNativeChurchReviveSuccess()
	if plan.StartMusicTrack != 17 || plan.ReturnMusicTrack != 11 ||
		plan.MusicLoopCount != 1 ||
		plan.AnimationDelayBIOSTicks != 2 || plan.PaletteDelayMS != 4 ||
		plan.RiseLatchBIOSTicks != 10 || plan.FallLatchBIOSTicks != 5 ||
		len(plan.RisePaletteDeltas) != 32 || len(plan.FallPaletteDeltas) != 32 ||
		plan.RisePaletteDeltas[0] != 0 || plan.RisePaletteDeltas[31] != 62 ||
		plan.FallPaletteDeltas[0] != 62 || plan.FallPaletteDeltas[31] != 0 {
		t.Fatalf("unexpected revive success plan: %#v", plan)
	}
}

func TestNativeChurchReviveSuccessUsesPlayerOriginalEntries23Through31(t *testing.T) {
	const base = "../../../org_game/炎龍騎士團/FLAME2"
	fdotherPath := filepath.Join(base, "FDOTHER.DAT")
	datoPath := filepath.Join(base, "DATO.DAT")
	if _, err := os.Stat(fdotherPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	resource, err := fdother.ReadResource(fdotherPath, 14)
	if err != nil {
		t.Fatal(err)
	}
	frames := make([]fdother.Frame, 9)
	for i := range frames {
		frames[i], err = fdother.ParseLMI1FrameEntry(resource, 23+i)
		if err != nil {
			t.Fatalf("entry %d: %v", 23+i, err)
		}
	}
	portraits, err := dato.DecodeResource(datoPath, 131)
	if err != nil {
		t.Fatal(err)
	}
	background := make([]byte, 320*200)
	animation, final, err := ComposeNativeChurchReviveSuccessFrames(
		background, frames, portraits[0],
	)
	if err != nil {
		t.Fatal(err)
	}
	changed := 0
	for _, frame := range animation {
		for _, pixel := range frame {
			if pixel != 0 {
				changed++
			}
		}
	}
	if changed == 0 || len(final) != 320*200 {
		t.Fatalf("original revive effect changed=%d final=%d", changed, len(final))
	}
}

func TestComposeNativeChurchReviveSuccessFramesAccumulatesAndRestoresPortrait(t *testing.T) {
	frames := make([]fdother.Frame, 9)
	for i := range frames {
		frames[i] = fdother.Frame{
			Width: 1, Height: 1,
			Pixels: []byte{1, 0, 1, 0, 0, byte(i + 1)},
		}
	}
	portrait := dato.Frame{Width: 1, Height: 1, Pixels: []byte{77}}
	animation, final, err := ComposeNativeChurchReviveSuccessFrames(
		make([]byte, 320*200), frames, portrait,
	)
	if err != nil {
		t.Fatal(err)
	}
	const effectOffset = 32*320 + 147
	if len(animation) != 9 || animation[0][effectOffset] != 1 ||
		animation[8][effectOffset] != 9 {
		t.Fatalf("animation accumulation is wrong: frames=%d first=%d last=%d",
			len(animation), animation[0][effectOffset], animation[8][effectOffset])
	}
	if final[4*320+118] != 77 || animation[8][4*320+118] != 0 {
		t.Fatalf("portrait restore final=%d prior=%d",
			final[4*320+118], animation[8][4*320+118])
	}
}
