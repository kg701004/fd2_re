package fdicon

import "testing"

func TestCopyNativeIndexedRegionMatches11EB0(t *testing.T) {
	src := []byte{
		0, 1, 2, 3, 4, 5,
		6, 7, 8, 9, 10, 11,
	}
	dst := make([]byte, 12)
	if err := CopyNativeIndexedRegion(dst, 6, src[1:], 6, 4, 2); err != nil {
		t.Fatal(err)
	}
	want := []byte{1, 2, 3, 4, 0, 0, 7, 8, 9, 10, 0, 0}
	for i := range want {
		if dst[i] != want[i] {
			t.Fatalf("dst[%d]=%d want=%d", i, dst[i], want[i])
		}
	}
	if err := CopyNativeIndexedRegion(make([]byte, 3), 3, src, 6, 4, 1); err == nil {
		t.Fatal("short destination accepted")
	}
	if err := CopyNativeIndexedRegion(dst, 3, src, 6, 4, 1); err == nil {
		t.Fatal("short stride accepted")
	}
}
