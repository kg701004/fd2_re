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
	MetadataSize = SlotSize - RosterSize
)

var ErrEmptyChapterSlot = errors.New("fdsave: native chapter slot is empty")

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
	if len(replacement.Metadata) != MetadataSize {
		return nil, fmt.Errorf("fdsave: metadata size=%#x, want %#x", len(replacement.Metadata), MetadataSize)
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
	if len(s.Metadata) != MetadataSize {
		return VerifiedMetadata{}, errors.New("fdsave: invalid metadata size")
	}
	return VerifiedMetadata{
		Chapter:     s.Metadata[0],
		RosterCount: s.Metadata[1],
		Currency:    binary.LittleEndian.Uint32(s.Metadata[2:6]),
	}, nil
}

// PersistentRecord preserves one exact native 0x50-byte roster record.
//
// Individual offsets must be decoded only after their writer and consumer are
// proven. Keeping the complete record is required because native 0x2604a copies
// all 32 records before loading the selected slot's metadata.
type PersistentRecord struct {
	Raw [UnitSize]byte
}

// ChapterSlotSnapshot is the safe import boundary for one native chapter slot.
// It mirrors the selected record copied by 0x2602c..0x26098, while retaining
// opaque bytes instead of guessing normalized campaign or battle semantics.
//
// The RosterCount capacity check is a remake safety invariant. The native load
// path copies the fixed 0xa00-byte roster and does not establish that check.
type ChapterSlotSnapshot struct {
	Slot     int
	Verified VerifiedMetadata
	Metadata [MetadataSize]byte
	Records  [RosterUnits]PersistentRecord
}

// InspectChapterSlot validates and copies a non-empty native chapter slot.
// It does not convert persistent records to battle.Unit and therefore cannot
// by itself be used to claim successful native campaign restore.
func InspectChapterSlot(plain []byte, slot int) (ChapterSlotSnapshot, error) {
	raw, err := ReadSlot(plain, slot)
	if err != nil {
		return ChapterSlotSnapshot{}, err
	}
	verified, err := ReadVerifiedMetadata(plain, slot)
	if err != nil {
		return ChapterSlotSnapshot{}, err
	}
	if verified.Chapter == 0xff {
		return ChapterSlotSnapshot{}, ErrEmptyChapterSlot
	}
	if int(verified.RosterCount) > RosterUnits {
		return ChapterSlotSnapshot{}, fmt.Errorf(
			"fdsave: roster count %d exceeds native capacity %d",
			verified.RosterCount, RosterUnits,
		)
	}
	var snapshot ChapterSlotSnapshot
	snapshot.Slot = slot
	snapshot.Verified = verified
	copy(snapshot.Metadata[:], raw.Metadata)
	for index := range snapshot.Records {
		start := index * UnitSize
		copy(snapshot.Records[index].Raw[:], raw.Roster[start:start+UnitSize])
	}
	return snapshot, nil
}

// ActiveRecords returns a copy of the count-delimited prefix selected by the
// native metadata. The remaining fixed-capacity records stay available in
// Records for exact preservation and future evidence work.
func (s ChapterSlotSnapshot) ActiveRecords() []PersistentRecord {
	count := int(s.Verified.RosterCount)
	if count < 0 || count > len(s.Records) {
		return nil
	}
	out := make([]PersistentRecord, count)
	copy(out, s.Records[:count])
	return out
}
