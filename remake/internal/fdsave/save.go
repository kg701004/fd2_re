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

	CurrentPersistentRosterOffset = 0x08a3
	CurrentRuntimeRosterOffset    = 0x12a3
	CurrentRuntimeHeaderOffset    = 0x30c3
	CurrentRuntimeHeaderSize      = 18
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

// PersistentInventoryCell is one exact two-byte native item cell. Flags remain
// raw because only individual consumers, such as the equipped 0x40 bit, have
// closed meaning.
type PersistentInventoryCell struct {
	Flags  byte
	ItemID byte
}

// PersistentRecordView exposes only offsets with direct constructor and UI
// consumers. RawPresentationKey is deliberately not named portrait, map slot,
// or character identity; native code uses it as a mutable resource key while
// RawIdentity has the separate +8 roster lookup contract.
type PersistentRecordView struct {
	RawByte5           byte
	RawCamp            byte
	RawPresentationKey byte
	RawIdentity        byte
	Inventory          [8]PersistentInventoryCell
	CommandMask        [5]byte
	Race               byte
	Class              byte
	Level              byte
	Transient          [6]byte
	BaseAP             int16
	BaseDP             int16
	Movement           byte
	Experience         byte
	DX                 int16
	HP                 int16
	MaxHP              int16
	MP                 int16
	MaxMP              int16
	AP                 int16
	DP                 int16
	HIT                int16
	EV                 int16
}

// View decodes the proven read-only field projection of one native persistent
// record. The complete byte array remains authoritative and is never mutated.
func (r PersistentRecord) View() PersistentRecordView {
	var view PersistentRecordView
	view.RawByte5 = r.Raw[5]
	view.RawCamp = r.Raw[6]
	view.RawPresentationKey = r.Raw[7]
	view.RawIdentity = r.Raw[8]
	for slot := range view.Inventory {
		offset := 0x0a + slot*2
		view.Inventory[slot] = PersistentInventoryCell{
			Flags:  r.Raw[offset],
			ItemID: r.Raw[offset+1],
		}
	}
	copy(view.CommandMask[:], r.Raw[0x1a:0x1f])
	view.Race = r.Raw[0x1f]
	view.Class = r.Raw[0x20]
	view.Level = r.Raw[0x21]
	copy(view.Transient[:], r.Raw[0x22:0x28])
	view.BaseAP = persistentRecordI16(r.Raw[:], 0x37)
	view.BaseDP = persistentRecordI16(r.Raw[:], 0x39)
	view.Movement = r.Raw[0x3b]
	view.Experience = r.Raw[0x3c]
	view.DX = persistentRecordI16(r.Raw[:], 0x3e)
	view.HP = persistentRecordI16(r.Raw[:], 0x40)
	view.MaxHP = persistentRecordI16(r.Raw[:], 0x42)
	view.MP = persistentRecordI16(r.Raw[:], 0x44)
	view.MaxMP = persistentRecordI16(r.Raw[:], 0x46)
	view.AP = persistentRecordI16(r.Raw[:], 0x48)
	view.DP = persistentRecordI16(r.Raw[:], 0x4a)
	view.HIT = persistentRecordI16(r.Raw[:], 0x4c)
	view.EV = persistentRecordI16(r.Raw[:], 0x4e)
	return view
}

func persistentRecordI16(record []byte, offset int) int16 {
	return int16(binary.LittleEndian.Uint16(record[offset:]))
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

// CurrentRuntimeHeader is the 18-byte header restored by native 0x10010.
// TurnCounter and both count fields are fixed by direct writes to
// [0x53bef], [0x53beb], and [0x53bfb]. The four trailing option bytes remain
// raw except for HUDGateA, whose system-menu writer and renderer consumer are
// independently closed.
type CurrentRuntimeHeader struct {
	TurnCounter     byte
	RuntimeCount    byte
	Chapter         byte
	CameraX         byte
	CameraY         byte
	CursorX         byte
	CursorY         byte
	VisibleCursorX  byte
	VisibleCursorY  byte
	PersistentCount byte
	Currency        uint32
	Raw53AF9        byte
	HUDGateA        byte
	Raw51E61        byte
	Raw51E62        byte
}

// CurrentSnapshot preserves the two exact roster regions consumed by
// 0x10010. RuntimeRecords is count-delimited; PersistentRecords retains the
// full native capacity because the loader copies a fixed 0xa00 bytes.
type CurrentSnapshot struct {
	Header            CurrentRuntimeHeader
	PersistentRecords [RosterUnits]PersistentRecord
	RuntimeRecords    []PersistentRecord
}

// InspectCurrentSnapshot decodes only the verified plaintext layout used by
// the title CONTINUE branch. It is separate from the four chapter slots.
func InspectCurrentSnapshot(plain []byte) (CurrentSnapshot, error) {
	if len(plain) != FileSize {
		return CurrentSnapshot{}, errors.New("fdsave: invalid plaintext size")
	}
	header := plain[CurrentRuntimeHeaderOffset : CurrentRuntimeHeaderOffset+CurrentRuntimeHeaderSize]
	if int(header[1]) > RosterUnits*3 {
		return CurrentSnapshot{}, fmt.Errorf(
			"fdsave: runtime count %d exceeds native capacity %d",
			header[1], RosterUnits*3,
		)
	}
	if int(header[9]) > RosterUnits {
		return CurrentSnapshot{}, fmt.Errorf(
			"fdsave: persistent count %d exceeds native capacity %d",
			header[9], RosterUnits,
		)
	}
	snapshot := CurrentSnapshot{
		Header: CurrentRuntimeHeader{
			TurnCounter:     header[0],
			RuntimeCount:    header[1],
			Chapter:         header[2],
			CameraX:         header[3],
			CameraY:         header[4],
			CursorX:         header[5],
			CursorY:         header[6],
			VisibleCursorX:  header[7],
			VisibleCursorY:  header[8],
			PersistentCount: header[9],
			Currency:        binary.LittleEndian.Uint32(header[10:14]),
			Raw53AF9:        header[14],
			HUDGateA:        header[15],
			Raw51E61:        header[16],
			Raw51E62:        header[17],
		},
	}
	for index := range snapshot.PersistentRecords {
		start := CurrentPersistentRosterOffset + index*UnitSize
		copy(
			snapshot.PersistentRecords[index].Raw[:],
			plain[start:start+UnitSize],
		)
	}
	snapshot.RuntimeRecords = make(
		[]PersistentRecord, int(snapshot.Header.RuntimeCount),
	)
	for index := range snapshot.RuntimeRecords {
		start := CurrentRuntimeRosterOffset + index*UnitSize
		copy(snapshot.RuntimeRecords[index].Raw[:], plain[start:start+UnitSize])
	}
	return snapshot, nil
}

// ActivePersistentRecords returns a copy of the header-delimited current
// persistent roster.
func (s CurrentSnapshot) ActivePersistentRecords() []PersistentRecord {
	count := int(s.Header.PersistentCount)
	if count < 0 || count > len(s.PersistentRecords) {
		return nil
	}
	out := make([]PersistentRecord, count)
	copy(out, s.PersistentRecords[:count])
	return out
}
