package fdother

import (
	"encoding/binary"
	"testing"
)

func TestParseLMI1NativeCodec(t *testing.T) {
	// Two entries: literal 0, literal 0xc0, then a 0xc3 repeat of 7.
	data := make([]byte, 6+2*4)
	copy(data, "LMI1")
	binary.LittleEndian.PutUint16(data[4:], 2)
	first, second := 14, 22
	binary.LittleEndian.PutUint32(data[6:], uint32(first))
	binary.LittleEndian.PutUint32(data[10:], uint32(second))
	data = append(data, 3, 0, 1, 0, 0, 0xc0, 1, 2)
	data = append(data, 2, 0, 1, 0, 0xc2, 7)
	entries, err := ParseLMI1(data)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 2 || entries[0].Width != 3 || entries[0].Height != 1 {
		t.Fatalf("entries=%#v", entries)
	}
	want0 := []byte{0, 0xc0, 1}
	for i, v := range want0 {
		if entries[0].Pixels[i] != v {
			t.Fatalf("entry0 pixel %d=%#x, want %#x", i, entries[0].Pixels[i], v)
		}
	}
	if entries[1].Width != 2 || entries[1].Height != 1 || len(entries[1].Pixels) != 2 || entries[1].Pixels[0] != 7 || entries[1].Pixels[1] != 7 {
		t.Fatalf("entry1=%#v", entries[1])
	}
}

func TestParseLMI1RejectsMalformedCodec(t *testing.T) {
	data := make([]byte, 14)
	copy(data, "LMI1")
	binary.LittleEndian.PutUint16(data[4:], 1)
	binary.LittleEndian.PutUint32(data[6:], 10)
	binary.LittleEndian.PutUint16(data[10:], 2)
	binary.LittleEndian.PutUint16(data[12:], 1)
	if _, err := ParseLMI1(data); err == nil {
		t.Fatal("truncated LMI1 stream must fail closed")
	}
}
