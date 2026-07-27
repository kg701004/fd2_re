package fdother

import (
	"encoding/binary"
	"os"
	"testing"
)

func TestParseLUTBank(t *testing.T) {
	data := make([]byte, 6+2*4+2*256)
	copy(data, "LMI1")
	data[4] = 2
	binary.LittleEndian.PutUint32(data[6:], 14)
	binary.LittleEndian.PutUint32(data[10:], 14+256)
	data[14], data[14+256] = 7, 9
	luts, err := ParseLUTBank(data)
	if err != nil || len(luts) != 2 || len(luts[0]) != 256 || luts[0][0] != 7 || luts[1][0] != 9 {
		t.Fatalf("luts=%#v err=%v", luts, err)
	}
	if _, err := ParseLUTBank(data[:20]); err == nil {
		t.Fatal("truncated LUT bank accepted")
	}
}

func TestNativeUnitPresentBridgeLUTCrossesEntryBoundary(t *testing.T) {
	luts := [][]byte{make([]byte, 256), make([]byte, 256)}
	for i := range luts[0] {
		luts[0][i] = byte(i)
	}
	luts[1][0] = 0xa7
	bridge, err := NativeUnitPresentBridgeLUT(luts)
	if err != nil {
		t.Fatal(err)
	}
	if bridge[0] != 1 || bridge[254] != 255 || bridge[255] != 0xa7 {
		t.Fatalf("shifted bridge boundaries=%#x/%#x/%#x", bridge[0], bridge[254], bridge[255])
	}
	if _, err := NativeUnitPresentBridgeLUT(luts[:1]); err == nil {
		t.Fatal("accepted bridge source without adjacent entry")
	}
}

func TestFDOTHER003LUTBank(t *testing.T) {
	const path = "../../../org_game/炎龍騎士團/FLAME2/FDOTHER.DAT"
	if _, err := os.Stat(path); os.IsNotExist(err) {
		t.Skip("player-provided FDOTHER.DAT is absent")
	}
	luts, err := DecodeLUTResource(path, 3)
	if err != nil {
		t.Fatal(err)
	}
	if len(luts) != 23 {
		t.Fatalf("FDOTHER#3 LUT count=%d, want 23", len(luts))
	}
	for i, lut := range luts {
		if len(lut) != 256 {
			t.Fatalf("FDOTHER#3 LUT %d length=%d", i, len(lut))
		}
	}
	bridge, err := NativeUnitPresentBridgeLUT(luts)
	if err != nil {
		t.Fatal(err)
	}
	if bridge[0] != luts[0][1] || bridge[254] != luts[0][255] || bridge[255] != luts[1][0] {
		t.Fatal("real FDOTHER#3 bridge LUT does not match entry0 pointer+1")
	}
	if string(bridge) == string(luts[0]) || string(bridge) == string(luts[1]) {
		t.Fatal("real bridge LUT incorrectly aliases an aligned directory entry")
	}
}
