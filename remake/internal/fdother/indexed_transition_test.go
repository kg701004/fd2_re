package fdother

import "testing"

func TestApplyIndexedTransitionPassPreservesRadialRedrawOrdering(t *testing.T) {
	dst := make([]byte, 8*8)
	for i := range dst {
		dst[i] = byte(i)
	}
	lut := make([]byte, 256)
	for i := range lut {
		lut[i] = byte(255 - i)
	}
	pass := IndexedTransitionPass{
		FirstRadial:  RadialLUTRemap{CenterX: 3, CenterY: 3, Radius: 3, Scale: 10, StartY: 0, EndY: 8, ClipWidth: 8},
		SecondRadial: RadialLUTRemap{CenterX: 3, CenterY: 3, Radius: 2, Scale: 10, StartY: 0, EndY: 8, ClipWidth: 8},
		FinalRect:    CenteredRectLUTRemap{CenterX: 3, HorizontalRadius: 2, StartY: 0, EndY: 8, ClipWidth: 8},
	}
	order := []string{}
	if err := ApplyIndexedTransitionPass(dst, 8, lut, pass, func(buf []byte) error {
		order = append(order, "redraw")
		buf[0] = 0x7e
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if len(order) != 1 || dst[0] != 0x7e {
		t.Fatalf("redraw ordering=%v first-byte=%#x", order, dst[0])
	}
}

func TestApplyIndexedTransitionPassRejectsMissingRedrawBeforeMutation(t *testing.T) {
	dst := make([]byte, 64)
	dst[0] = 7
	pass := IndexedTransitionPass{
		FirstRadial:  RadialLUTRemap{CenterX: 1, CenterY: 1, Radius: 1, Scale: 10, EndY: 8, ClipWidth: 8},
		SecondRadial: RadialLUTRemap{CenterX: 1, CenterY: 1, Radius: 1, Scale: 10, EndY: 8, ClipWidth: 8},
		FinalRect:    CenteredRectLUTRemap{CenterX: 1, HorizontalRadius: 1, EndY: 8, ClipWidth: 8},
	}
	if err := ApplyIndexedTransitionPass(dst, 8, make([]byte, 256), pass, nil); err == nil {
		t.Fatal("missing redraw callback accepted")
	}
	if dst[0] != 7 {
		t.Fatal("missing redraw mutated buffer")
	}
}

func TestApplyIndexedTransitionPassPreflightsSecondPass(t *testing.T) {
	dst := make([]byte, 64)
	dst[0] = 9
	pass := IndexedTransitionPass{
		FirstRadial:  RadialLUTRemap{CenterX: 1, CenterY: 1, Radius: 1, Scale: 10, EndY: 8, ClipWidth: 8},
		SecondRadial: RadialLUTRemap{CenterX: 9, CenterY: 1, Radius: 1, Scale: 10, EndY: 8, ClipWidth: 8},
		FinalRect:    CenteredRectLUTRemap{CenterX: 1, HorizontalRadius: 1, EndY: 8, ClipWidth: 8},
	}
	if err := ApplyIndexedTransitionPass(dst, 8, make([]byte, 256), pass, func([]byte) error { return nil }); err == nil {
		t.Fatal("invalid second pass accepted")
	}
	if dst[0] != 9 {
		t.Fatal("invalid second pass mutated first pass")
	}
}
