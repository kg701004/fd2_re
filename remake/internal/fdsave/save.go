// Package fdsave preserves the proven FD2.SAV storage ABI without assigning
// gameplay meaning to the still-opaque roster bytes.
package fdsave

import (
	"encoding/binary"
	"errors"
	"fmt"
)

const (
	FileSize     = 0x59cb
	ChecksumOff  = FileSize - 4
	SlotOffset   = 0x312b
	SlotSize     = 0xa28
	SlotCount    = 4
	RosterSize   = 0xa00
	UnitSize     = 0x50
	RosterUnits  = RosterSize / UnitSize
	metadataSize = SlotSize - RosterSize
)

// Slot is one native logical record. Roster and Metadata remain raw because
// only a subset of metadata fields has proven meaning; callers must not
// reinterpret opaque bytes as normalized campaign state.
type Slot struct {
	Roster   []byte
	Metadata []byte
}

func rol16(v uint16, n uint) uint16 { return (v << n) | (v >> (16 - n)) }

// XOREnvelope applies native 0x4dbd8. It is its own inverse.
func XOREnvelope(data []byte) []byte {
	out := append([]byte(nil), data...)
	state := uint16(0x00a5)
	for i, b := range out {
		state = rol16(state+0x9014, 3)
		out[i] = b ^ byte(state)
	}
	return out
}

func Checksum(plain []byte) (uint32, error) {
	if len(plain) != FileSize {
		return 0, fmt.Errorf("fdsave: want %#x bytes, got %#x", FileSize, len(plain))
	}
	var sum uint32
	for _, b := range plain[:ChecksumOff] {
		sum += uint32(b)
	}
	return sum, nil
}

// Decode validates size, reverses the envelope, and verifies the trailing
// little-endian checksum. It never mutates the caller's buffer.
func Decode(stored []byte) ([]byte, error) {
	if len(stored) != FileSize {
		return nil, fmt.Errorf("fdsave: want %#x bytes, got %#x", FileSize, len(stored))
	}
	plain := XOREnvelope(stored)
	want := binary.LittleEndian.Uint32(plain[ChecksumOff:])
	got, _ := Checksum(plain)
	if got != want {
		return nil, fmt.Errorf("fdsave: checksum mismatch: expected %#08x, got %#08x", want, got)
	}
	return plain, nil
}

// Encode writes the native checksum and applies the reversible envelope.
func Encode(plain []byte) ([]byte, error) {
	if len(plain) != FileSize {
		return nil, fmt.Errorf("fdsave: want %#x bytes, got %#x", FileSize, len(plain))
	}
	out := append([]byte(nil), plain...)
	sum, _ := Checksum(out)
	binary.LittleEndian.PutUint32(out[ChecksumOff:], sum)
	return XOREnvelope(out), nil
}

func SlotBounds(slot int) (start, end int, err error) {
	if slot < 0 || slot >= SlotCount {
		return 0, 0, fmt.Errorf("fdsave: slot %d outside 0..%d", slot, SlotCount-1)
	}
	start = SlotOffset + slot*SlotSize
	return start, start + SlotSize, nil
}

// ReadSlot returns copies of the exact roster/metadata regions.
func ReadSlot(plain []byte, slot int) (Slot, error) {
	if len(plain) != FileSize {
		return Slot{}, errors.New("fdsave: invalid plaintext size")
	}
	start, end, err := SlotBounds(slot)
	if err != nil {
		return Slot{}, err
	}
	return Slot{
		Roster:   append([]byte(nil), plain[start:start+RosterSize]...),
		Metadata: append([]byte(nil), plain[start+RosterSize:end]...),
	}, nil
}

// WriteSlot replaces one native logical record in a plaintext save image.
// Roster and Metadata remain opaque byte regions; callers must use Encode
// afterward to rebuild the native checksum/envelope. Validation happens before
// copying so malformed editable input cannot partially mutate the image.
func WriteSlot(plain []byte, slot int, replacement Slot) ([]byte, error) {
	if len(plain) != FileSize {
		return nil, errors.New("fdsave: invalid plaintext size")
	}
	if len(replacement.Roster) != RosterSize {
		return nil, fmt.Errorf("fdsave: roster size=%#x, want %#x", len(replacement.Roster), RosterSize)
	}
	if len(replacement.Metadata) != metadataSize {
		return nil, fmt.Errorf("fdsave: metadata size=%#x, want %#x", len(replacement.Metadata), metadataSize)
	}
	start, end, err := SlotBounds(slot)
	if err != nil {
		return nil, err
	}
	out := append([]byte(nil), plain...)
	copy(out[start:start+RosterSize], replacement.Roster)
	copy(out[start+RosterSize:end], replacement.Metadata)
	return out, nil
}

// VerifiedMetadata exposes only fields whose address/dataflow is closed:
// chapter (+0), roster count (+1), and currency dword (+2..+5). The remaining
// metadata bytes are intentionally not surfaced with gameplay names.
type VerifiedMetadata struct {
	Chapter     byte
	RosterCount byte
	Currency    uint32
}

func ReadVerifiedMetadata(plain []byte, slot int) (VerifiedMetadata, error) {
	s, err := ReadSlot(plain, slot)
	if err != nil {
		return VerifiedMetadata{}, err
	}
	if len(s.Metadata) != metadataSize {
		return VerifiedMetadata{}, errors.New("fdsave: invalid metadata size")
	}
	return VerifiedMetadata{
		Chapter:     s.Metadata[0],
		RosterCount: s.Metadata[1],
		Currency:    binary.LittleEndian.Uint32(s.Metadata[2:6]),
	}, nil
}
