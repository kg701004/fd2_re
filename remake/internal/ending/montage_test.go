package ending

import "testing"

func TestNative2C548MontageMapPlansNativePartySlotOrder(t *testing.T) {
	montage, err := LoadMontage("../../assets/endings/native_2c548.json")
	if err != nil {
		t.Fatal(err)
	}
	plans, err := montage.PlanPartyCycle([]byte{4, 0, 96})
	if err != nil {
		t.Fatal(err)
	}
	if len(plans) != 3 || plans[0] != (PartyCyclePlan{LoopIndex: 2, UnitSlot: 2, VisualGroup: 96, PrimaryFIGANI: 289, SecondaryFIGANI: 288, Frames: 20, FrameDelayMS: 1}) || plans[1].LoopIndex != 1 || plans[1].UnitSlot != 0 || plans[1].PrimaryFIGANI != 13 || plans[2].LoopIndex != 0 || plans[2].UnitSlot != 1 || plans[2].PrimaryFIGANI != 1 || plans[2].SecondaryFIGANI != 0 {
		t.Fatalf("party plans = %#v", plans)
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
	plan, err = montage.PlanPortraitText(unit, 0xdc)
	if err != nil || plan.Epilogue.Index != 0x2d {
		t.Fatalf("special epilogue plan = %#v err=%v", plan, err)
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
