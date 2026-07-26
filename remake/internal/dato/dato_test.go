package dato

import (
	"encoding/binary"
	"os"
	"testing"
)

func TestParseDATOHighRunAndOpaqueZero(t *testing.T) {
	data := make([]byte, 16+4*(4+4))
	for i := 0; i < 4; i++ {
		binary.LittleEndian.PutUint32(data[i*4:], uint32(16+i*8))
		binary.LittleEndian.PutUint16(data[16+i*8:], 2)
		binary.LittleEndian.PutUint16(data[18+i*8:], 2)
		copy(data[20+i*8:], []byte{0xc2, byte(i + 1), 0})
	}
	frames, err := ParseResource(data)
	if err != nil {
		t.Fatal(err)
	}
	if len(frames) != 4 || frames[0].Pixels[0] != 1 || frames[0].Pixels[1] != 1 || frames[0].Pixels[2] != 0 || frames[3].Pixels[0] != 4 {
		t.Fatalf("frames=%#v", frames)
	}
	dst := []byte{9, 9, 9, 9}
	if err := frames[0].BlitAt(dst, 2, 0, 0); err != nil {
		t.Fatal(err)
	}
	if dst[0] != 1 || dst[1] != 1 || dst[2] != 0 || dst[3] != 0 {
		t.Fatalf("opaque blit=%v", dst)
	}
}

func TestDATOPlayerResourceIfPresent(t *testing.T) {
	path := "../../../org_game/炎龍騎士團/FLAME2/DATO.DAT"
	if _, err := os.Stat(path); err != nil {
		t.Skip("player-provided DATO.DAT is absent")
	}
	frames, err := DecodeResource(path, 37)
	if err != nil {
		t.Fatal(err)
	}
	if len(frames) != 4 || frames[0].Width != 80 || frames[0].Height != 80 || len(frames[0].Pixels) != 6400 {
		t.Fatalf("DATO#37=%#v", frames)
	}
}
