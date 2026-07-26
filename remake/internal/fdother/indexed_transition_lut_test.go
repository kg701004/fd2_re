package fdother

import "testing"

func TestNativeIndexedTransitionLUTResolvesOnlyOuterPassRange(t *testing.T) {
	bank := make([][]byte, 10)
	for i := range bank {
		bank[i] = make([]byte, 256)
		bank[i][0] = byte(i)
	}
	got, err := NativeIndexedTransitionLUT(bank, 9)
	if err != nil || got[0] != 9 {
		t.Fatalf("descriptor 9=%d err=%v", got[0], err)
	}
	got[0] = 0xff
	if bank[9][0] != 9 {
		t.Fatal("selector returned mutable bank storage")
	}
	for _, descriptor := range []int{0, 10, -1} {
		if _, err := NativeIndexedTransitionLUT(bank, descriptor); err == nil {
			t.Fatalf("descriptor %d accepted", descriptor)
		}
	}
}

func TestNativeIndexedTransitionLUTRejectsMalformedEntry(t *testing.T) {
	bank := make([][]byte, 10)
	bank[1] = make([]byte, 255)
	if _, err := NativeIndexedTransitionLUT(bank, 1); err == nil {
		t.Fatal("short LUT accepted")
	}
}
