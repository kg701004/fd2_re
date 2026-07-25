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
}
