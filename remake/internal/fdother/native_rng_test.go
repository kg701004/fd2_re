package fdother

import "testing"

func TestNativeRNGStepUses16BitAddAndRotate(t *testing.T) {
	if got := NativeRNGStep(0); got != 0x80a4 {
		t.Fatalf("step(0) = %#x", got)
	}
	if got := NativeRNGStep(0x1234); got != 0x1245 {
		t.Fatalf("step(0x1234) = %#x", got)
	}
}

func TestNativeRNGMarkerUsesRemainderNotQuotient(t *testing.T) {
	if got := NativeRNGMarker(0); got != 2 || NativeRNGMarker(0x1234) != 3 {
		t.Fatalf("markers = %#x %#x", NativeRNGMarker(0), NativeRNGMarker(0x1234))
	}
}
