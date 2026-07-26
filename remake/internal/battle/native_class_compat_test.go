package battle

import "testing"

func TestNativeClassCompatibilityRowOffset(t *testing.T) {
	for _, tc := range []struct {
		classID int
		want    int
	}{
		{0, 0}, {1, 7}, {0xff, 0xff * 7},
	} {
		got, err := NativeClassCompatibilityRowOffset(tc.classID)
		if err != nil || got != tc.want {
			t.Fatalf("class %#x: got %#x err=%v want %#x", tc.classID, got, err, tc.want)
		}
	}
	for _, classID := range []int{-1, 0x100} {
		if _, err := NativeClassCompatibilityRowOffset(classID); err == nil {
			t.Fatalf("class %#x unexpectedly accepted", classID)
		}
	}
}

func TestNativeClassItemCompatibleUsesExactlySixBytes(t *testing.T) {
	row := []byte{2, 4, 8, 16, 32, 64, 0xff}
	for _, item := range []byte{2, 64} {
		ok, err := NativeClassItemCompatible(item, row)
		if err != nil || !ok {
			t.Fatalf("item %#x: ok=%v err=%v", item, ok, err)
		}
	}
	if ok, err := NativeClassItemCompatible(0xff, row); err != nil || ok {
		t.Fatalf("seventh byte must not participate: ok=%v err=%v", ok, err)
	}
	if _, err := NativeClassItemCompatible(2, row[:5]); err == nil {
		t.Fatal("short row unexpectedly accepted")
	}
}
