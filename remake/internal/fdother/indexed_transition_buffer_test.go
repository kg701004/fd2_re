package fdother

import "testing"

func TestCopyNativeTransitionBufferPreservesFullSeed(t *testing.T) {
	src := []byte{1, 2, 3, 4}
	dst := make([]byte, 8)
	if err := CopyNativeTransitionBuffer(dst, src); err != nil {
		t.Fatal(err)
	}
	for i, want := range src {
		if dst[i] != want {
			t.Fatalf("seed[%d]=%d want %d", i, dst[i], want)
		}
	}
	if dst[7] != 0 {
		t.Fatal("copy escaped source length")
	}
}

func TestCopyNativeTransitionViewportUsesNativeStrides(t *testing.T) {
	src := make([]byte, 4*6)
	for i := range src {
		src[i] = byte(i + 1)
	}
	dst := make([]byte, 4*4)
	if err := CopyNativeTransitionViewport(dst, 4, src, 1, 6, 3, 2); err != nil {
		t.Fatal(err)
	}
	for i, want := range []byte{2, 3, 4} {
		if dst[i] != want {
			t.Fatalf("viewport row0 byte %d=%d want %d", i, dst[i], want)
		}
	}
	for i, want := range []byte{8, 9, 10} {
		if dst[4+i] != want {
			t.Fatalf("viewport row1 byte %d=%d want %d", i, dst[4+i], want)
		}
	}
}

func TestCopyNativeTransitionViewportRejectsBeforeMutation(t *testing.T) {
	dst := []byte{9, 9, 9, 9}
	snapshot := append([]byte(nil), dst...)
	if err := CopyNativeTransitionViewport(dst, 2, []byte{1, 2}, 0, 2, 3, 1); err == nil {
		t.Fatal("invalid width accepted")
	}
	for i := range dst {
		if dst[i] != snapshot[i] {
			t.Fatal("invalid geometry mutated destination")
		}
	}
}
