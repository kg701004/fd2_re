package ending

import (
	"bytes"
	"os"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/dato"
	"github.com/wicanr2/fd2_re/remake/internal/fdother"
	"github.com/wicanr2/fd2_re/remake/internal/fdtxt"
)

func TestNative2C548MontageMapPlansNativePartySlotOrder(t *testing.T) {
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	plans, err := montage.PlanPartyCycle([]byte{4, 0, 96})
	if err != nil {
		t.Fatal(err)
	}
	if len(plans) != 3 || plans[0] != (PartyCyclePlan{LoopIndex: 2, UnitSlot: 2, VisualGroup: 96, PrimaryFIGANI: 289, SecondaryFIGANI: 288, Frames: 20, FrameDelayTicks: 1}) || plans[1].LoopIndex != 1 || plans[1].UnitSlot != 0 || plans[1].PrimaryFIGANI != 13 || plans[2].LoopIndex != 0 || plans[2].UnitSlot != 1 || plans[2].PrimaryFIGANI != 1 || plans[2].SecondaryFIGANI != 0 {
		t.Fatalf("party plans = %#v", plans)
	}
}

func TestNative2C548PortraitCountdownMatchesZeroResetAndMouthFrames(t *testing.T) {
	state := MontagePortraitState{}
	frame, err := state.Step(0xff)
	if err != nil || frame != NativeMontagePortraitNormalFrame || state.Countdown != 0x47 {
		t.Fatalf("reset frame=%d countdown=%d err=%v", frame, state.Countdown, err)
	}
	state.Countdown = 2
	frame, err = state.Step(0)
	if err != nil || frame != NativeMontagePortraitMouthFrame || state.Countdown != 1 {
		t.Fatalf("mouth1 frame=%d countdown=%d err=%v", frame, state.Countdown, err)
	}
	frame, err = state.Step(0)
	if err != nil || frame != NativeMontagePortraitMouthFrame || state.Countdown != 0 {
		t.Fatalf("mouth0 frame=%d countdown=%d err=%v", frame, state.Countdown, err)
	}
	frame, err = state.Step(0)
	if err != nil || frame != NativeMontagePortraitNormalFrame || state.Countdown != 0x28 {
		t.Fatalf("next reset frame=%d countdown=%d err=%v", frame, state.Countdown, err)
	}
	state.Countdown = 0x48
	if _, err := state.Step(0); err == nil {
		t.Fatal("invalid native countdown accepted")
	}
}

func TestNative2C548PortraitDurationMakesOnlyLoopZeroReachSpecialText(t *testing.T) {
	if got, err := NativeMontagePortraitIterations(1); err != nil || got != 0xdc {
		t.Fatalf("regular iterations=%d err=%v", got, err)
	}
	if got, err := NativeMontagePortraitIterations(0); err != nil || got != 0x1b8 {
		t.Fatalf("final iterations=%d err=%v", got, err)
	}
	if _, err := NativeMontagePortraitIterations(-1); err == nil {
		t.Fatal("negative loop index accepted")
	}
}

func TestComposeNative2C548PortraitFrameWithPlayerResources(t *testing.T) {
	const (
		base        = "../../../org_game/炎龍騎士團/FLAME2/"
		fdotherPath = base + "FDOTHER.DAT"
		fdtxtPath   = base + "FDTXT.DAT"
		datoPath    = base + "DATO.DAT"
	)
	for _, path := range []string{fdotherPath, fdtxtPath, datoPath} {
		if _, err := os.Stat(path); err != nil {
			t.Skip("player-provided original archives are absent")
		}
	}
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	restore := make([]byte, Bytes)
	if err := RenderDialogueFrameGridResource(*montage, fdotherPath, restore); err != nil {
		t.Fatal(err)
	}
	originalRestore := append([]byte(nil), restore...)
	portraits, err := dato.DecodeResource(datoPath, 37)
	if err != nil {
		t.Fatal(err)
	}
	currentRaw, err := fdother.ReadResource(fdtxtPath, 31)
	if err != nil {
		t.Fatal(err)
	}
	current, err := fdtxt.Parse(currentRaw)
	if err != nil {
		t.Fatal(err)
	}
	permanentRaw, err := fdother.ReadResource(fdtxtPath, 0)
	if err != nil {
		t.Fatal(err)
	}
	permanent, err := fdtxt.Parse(permanentRaw)
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
	unit := make([]byte, 0x21)
	unit[7], unit[8], unit[0x20] = 37, 4, 2
	normal, err := ComposeMontagePortraitFrame(*montage, restore, unit, 0, 0, portraits, current, permanent, font)
	if err != nil {
		t.Fatal(err)
	}
	mouth, err := ComposeMontagePortraitFrame(*montage, restore, unit, 0xdc, 3, portraits, current, permanent, font)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(restore, originalRestore) {
		t.Fatal("portrait composition mutated restore snapshot")
	}
	if len(normal) != Bytes || len(mouth) != Bytes || bytes.Equal(normal, mouth) {
		t.Fatal("original portrait frames were not independently composed")
	}
	for _, frame := range [][]byte{normal, mouth} {
		visible := 0
		for _, pixel := range frame {
			if pixel == 0xcd || pixel == 0x4c {
				visible++
			}
		}
		if visible == 0 {
			t.Fatal("native montage text colors are absent")
		}
	}
}

func TestNative2C548MontageRefusesEmptyParty(t *testing.T) {
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	if plans, err := montage.PlanPartyCycle([]byte{4}); err == nil || plans != nil {
		t.Fatalf("plans=%#v err=%v", plans, err)
	}
}

func TestNative2C548PortraitTextUsesEDIForSpecialEpilogue(t *testing.T) {
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	unit := make([]byte, 0x21)
	unit[7], unit[8], unit[0x20] = 37, 4, 2
	plan, err := montage.PlanPortraitText(unit, 0xdb)
	if err != nil {
		t.Fatal(err)
	}
	if plan.PortraitID != 37 || plan.CharacterName.Index != 5 || plan.ClassName.Index != 0x98 || plan.Epilogue.Index != 0x10 || plan.Epilogue.Destination != 0x7d08 {
		t.Fatalf("portrait plan = %#v", plan)
	}
	if montage.PartyCycle.DialogueFrameLayout.Stride != 320 || montage.PartyCycle.DialogueFrameLayout.Resource != 5 || montage.PartyCycle.DialogueFrameLayout.Arg8 != 5 || montage.PartyCycle.DialogueFrameLayout.ArgC != 7 || montage.PartyCycle.DialogueFrameLayout.Arg10 != 5 || montage.PartyCycle.DialogueFrameLayout.Arg14 != 5 || montage.PartyCycle.DialogueFrameLayout.Destination != "portrait_restore_buffer_C" {
		t.Fatalf("dialogue frame layout = %#v", montage.PartyCycle.DialogueFrameLayout)
	}
	plan, err = montage.PlanPortraitText(unit, 0xdc)
	if err != nil || plan.Epilogue.Index != 0x2d {
		t.Fatalf("special epilogue plan = %#v err=%v", plan, err)
	}
}

func TestNative2C548DialogueFrameGridTranscribesAllRawCells(t *testing.T) {
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	cells, err := montage.PlanDialogueFrameGrid()
	if err != nil {
		t.Fatal(err)
	}
	if len(cells) != 49 || cells[0] != (DialogueFramePlacement{ResourceIndex: 1, DestinationByte: 2245}) || cells[1].ResourceIndex != 2 || cells[1].DestinationByte != 2328 {
		t.Fatalf("dialogue frame cells head=%#v len=%d", cells[:2], len(cells))
	}
	if cells[len(cells)-1].ResourceIndex != 13 || cells[len(cells)-1].DestinationByte != 23752 {
		t.Fatalf("dialogue frame cells tail=%#v", cells[len(cells)-1])
	}
}

func TestRenderDialogueFrameGridUsesRawOpaqueCopies(t *testing.T) {
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	cells := make([]fdother.RawCell, 18)
	for i := range cells {
		cells[i] = fdother.RawCell{Width: 1, Height: 1, Pixels: []byte{byte(i)}}
	}
	dst := make([]byte, Bytes)
	if err := RenderDialogueFrameGrid(*montage, cells, dst); err != nil {
		t.Fatal(err)
	}
	if dst[2245] != 1 || dst[2248] != 5 || dst[23752] != 13 {
		t.Fatalf("dialogue frame pixels=%d/%d/%d", dst[2245], dst[2248], dst[23752])
	}
}

func TestRenderDATOFrameAtKeepsCallerOffsetExplicit(t *testing.T) {
	dst := make([]byte, Bytes)
	frame := dato.Frame{Width: 2, Height: 1, Pixels: []byte{0, 7}}
	if err := RenderDATOFrameAt(dst, frame, 320, 0x0c88); err != nil {
		t.Fatal(err)
	}
	if dst[0x0c88] != 0 || dst[0x0c89] != 7 {
		t.Fatalf("DATO staging paste=%d/%d", dst[0x0c88], dst[0x0c89])
	}
}

func TestRenderDialogueFrameGridResourceUsesPlayerFDOTHERWhenPresent(t *testing.T) {
	const datPath = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(datPath); err != nil {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	dst := make([]byte, Bytes)
	if err := RenderDialogueFrameGridResource(*montage, datPath, dst); err != nil {
		t.Fatal(err)
	}
	nonzero := 0
	for _, v := range dst {
		if v != 0 {
			nonzero++
		}
	}
	if nonzero == 0 {
		t.Fatal("FDOTHER#5 dialogue frame grid remained empty")
	}
}

func TestNative2C548FigureFadeIsNineNonMirroredPasses(t *testing.T) {
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	passes, err := montage.PlanFigureFade(1)
	if err != nil {
		t.Fatal(err)
	}
	if len(passes) != 9 || passes[0] != (FigureFadePass{Stage: 8, SourceOffset: 80, PaletteDelta: 48}) || passes[8] != (FigureFadePass{Stage: 0, SourceOffset: 0, PaletteDelta: 0}) {
		t.Fatalf("fade passes=%#v", passes)
	}
	if passes, err := montage.PlanFigureFade(0); err == nil || passes != nil {
		t.Fatalf("mirrored passes=%#v err=%v", passes, err)
	}
	if montage.PartyCycle.MirrorBranch.RequiredUnitSide != 0 || montage.PartyCycle.MirrorBranch.PrimarySource != "staging+0x140-stage*10" || montage.PartyCycle.MirrorBranch.SecondaryWhen != "arg4==0" {
		t.Fatalf("mirror branch = %#v", montage.PartyCycle.MirrorBranch)
	}
	mirrorPasses, err := montage.PlanMirrorFigureFade(0, 0)
	if err != nil {
		t.Fatal(err)
	}
	if len(mirrorPasses) != 9 || mirrorPasses[0] != (MirrorFigureFadePass{Stage: 8, PrimarySourceOffset: 0xf0, PaletteDelta: 48, DrawSecondary: true, DrawPlatform: true}) || mirrorPasses[8].PrimarySourceOffset != 0x140 || !mirrorPasses[8].DrawSecondary {
		t.Fatalf("mirror passes = %#v", mirrorPasses)
	}
	mirrorPasses, err = montage.PlanMirrorFigureFade(0, 1)
	if err != nil || mirrorPasses[0].DrawSecondary || mirrorPasses[0].DrawPlatform {
		t.Fatalf("arg4-gated mirror passes = %#v err=%v", mirrorPasses, err)
	}
	if mirrorPasses, err := montage.PlanMirrorFigureFade(1, 0); err == nil || mirrorPasses != nil {
		t.Fatalf("wrong-side mirror passes = %#v err=%v", mirrorPasses, err)
	}
}
