package fdother

import "testing"

func TestRotateNativeCh23RowsWrapsBottomRowsToTop(t *testing.T) {
	buf := make([]byte, NativeCh23StageStride*NativeCh23StageHeight)
	for row := 0; row < NativeCh23StageHeight; row++ {
		buf[row*NativeCh23StageStride] = byte(row)
	}
	if err := RotateNativeCh23Rows(buf, 2); err != nil {
		t.Fatal(err)
	}
	if buf[0] != 190 || buf[NativeCh23StageStride] != 191 || buf[2*NativeCh23StageStride] != 0 || buf[3*NativeCh23StageStride] != 1 {
		t.Fatalf("rotated rows=%d,%d,%d,%d", buf[0], buf[NativeCh23StageStride], buf[2*NativeCh23StageStride], buf[3*NativeCh23StageStride])
	}
}

func TestRotateNativeCh23RowsRejectsInvalidWithoutMutation(t *testing.T) {
	buf := make([]byte, NativeCh23StageStride*NativeCh23StageHeight)
	buf[0], buf[len(buf)-1] = 7, 9
	want := append([]byte(nil), buf...)
	if err := RotateNativeCh23Rows(buf, NativeCh23StageHeight+1); err == nil {
		t.Fatal("invalid latch accepted")
	}
	for i := range buf {
		if buf[i] != want[i] {
			t.Fatalf("buffer mutated at %d", i)
		}
	}
}

func TestApplyNativeCh23PaletteCycleWritesOnlyNativeRange(t *testing.T) {
	dac := make([]byte, 256*3)
	for i := range dac {
		dac[i] = 63
	}
	if err := ApplyNativeCh23PaletteCycle(dac, 0); err != nil {
		t.Fatal(err)
	}
	if dac[0] != 63 || dac[0x1f*3] != 63 || dac[0x30*3] != 63 {
		t.Fatal("palette cycle modified an entry outside 0x20..0x2f")
	}
	if got := dac[0x20*3 : 0x20*3+3]; got[0] != 0x0e || got[1] != 0x15 || got[2] != 0x26 {
		t.Fatalf("palette phase0 entry=%#v", got)
	}
	if err := ApplyNativeCh23PaletteCycle(dac, 1); err != nil {
		t.Fatal(err)
	}
	if got := dac[0x20*3 : 0x20*3+3]; got[0] != 0x0d || got[1] != 0x14 || got[2] != 0x25 {
		t.Fatalf("palette phase1 entry=%#v", got)
	}
}

func TestApplyNativeCh23PaletteCycleRejectsInvalidAtomically(t *testing.T) {
	dac := make([]byte, 256*3)
	dac[0x20*3] = 11
	want := append([]byte(nil), dac...)
	if err := ApplyNativeCh23PaletteCycle(dac, 16); err == nil {
		t.Fatal("invalid palette phase accepted")
	}
	for i := range dac {
		if dac[i] != want[i] {
			t.Fatalf("palette mutated at %d", i)
		}
	}
}
