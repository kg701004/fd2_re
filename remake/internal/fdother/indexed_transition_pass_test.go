package fdother

import "testing"

func TestBuildNativeIndexedTransitionPassPreservesRawArgumentAliasing(t *testing.T) {
	pass, err := BuildNativeIndexedTransitionPass(6, 6, 10, 0, 192)
	if err != nil {
		t.Fatal(err)
	}
	if pass.FirstRadial.CenterX != 6 || pass.FirstRadial.CenterY != 6 || pass.FirstRadial.Scale != 16 || pass.FirstRadial.StartY != 0 || pass.FirstRadial.EndY != 192 {
		t.Fatalf("first radial=%#v", pass.FirstRadial)
	}
	if pass.SecondRadial.StartY != 6 || pass.SecondRadial.EndY != 192 {
		t.Fatalf("second radial=%#v", pass.SecondRadial)
	}
	if pass.FinalRect.HorizontalRadius != 16 || pass.FinalRect.StartY != 0 || pass.FinalRect.EndY != 6 {
		t.Fatalf("final rect=%#v", pass.FinalRect)
	}
}

func TestBuildNativeIndexedTransitionPassRejectsInvalidRawBounds(t *testing.T) {
	for _, args := range [][5]int{{-1, 6, 10, 0, 192}, {6, 6, 0, 0, 192}, {6, 6, 10, 193, 192}, {312, 6, 10, 0, 192}} {
		if _, err := BuildNativeIndexedTransitionPass(args[0], args[1], args[2], args[3], args[4]); err == nil {
			t.Fatalf("accepted invalid args=%v", args)
		}
	}
}
