package fdsave

import (
	"encoding/binary"
	"errors"
	"testing"
)

func TestNativeEnvelopeRoundTripAndChecksum(t *testing.T) {
	plain := make([]byte, FileSize)
	for i := range plain {
		plain[i] = byte(i*37 + 11)
	}
	stored, err := Encode(plain)
	if err != nil {
		t.Fatal(err)
	}
	if string(stored) == string(plain) {
		t.Fatal("envelope did not transform input")
	}
	got, err := Decode(stored)
	if err != nil {
		t.Fatal(err)
	}
	want := append([]byte(nil), plain...)
	sum, _ := Checksum(want)
	binary.LittleEndian.PutUint32(want[ChecksumOff:], sum)
	if string(got) != string(want) {
		t.Fatal("round-trip plaintext mismatch")
	}
}

func TestDecodeRejectsTamper(t *testing.T) {
	stored, err := Encode(make([]byte, FileSize))
	if err != nil {
		t.Fatal(err)
	}
	stored[0x123] ^= 1
	if _, err := Decode(stored); err == nil {
		t.Fatal("tampered save accepted")
	}
}

func TestSlotBoundsAndVerifiedMetadata(t *testing.T) {
	if start, end, err := SlotBounds(0); err != nil || start != 0x312b || end != 0x3b53 {
		t.Fatalf("slot0 bounds=%#x..%#x err=%v", start, end, err)
	}
	if _, _, err := SlotBounds(4); err == nil {
		t.Fatal("out-of-range slot accepted")
	}
	plain := make([]byte, FileSize)
	start, _, _ := SlotBounds(2)
	plain[start+RosterSize] = 0xff
	plain[start+RosterSize+1] = 7
	binary.LittleEndian.PutUint32(plain[start+RosterSize+2:], 0x12345678)
	copy(plain[start+RosterSize+6:], []byte{0xa1, 0xa2, 0xa3, 0xa4})
	meta, err := ReadVerifiedMetadata(plain, 2)
	if err != nil || meta != (VerifiedMetadata{
		Chapter: 0xff, RosterCount: 7, Currency: 0x12345678,
		HUDGateA: 0xa1, Raw53AF9: 0xa2, Raw51E61: 0xa3, Raw51E62: 0xa4,
	}) {
		t.Fatalf("metadata=%#v err=%v", meta, err)
	}
}

func TestWriteSlotPreservesOtherSlotsAndUsesOpaqueRegions(t *testing.T) {
	plain := make([]byte, FileSize)
	for i := range plain {
		plain[i] = byte(i * 13)
	}
	replacement := Slot{Roster: make([]byte, RosterSize), Metadata: make([]byte, MetadataSize)}
	for i := range replacement.Roster {
		replacement.Roster[i] = 0xa5
	}
	for i := range replacement.Metadata {
		replacement.Metadata[i] = 0x5a
	}
	got, err := WriteSlot(plain, 2, replacement)
	if err != nil {
		t.Fatal(err)
	}
	start, end, _ := SlotBounds(2)
	if got[start] != 0xa5 || got[end-1] != 0x5a {
		t.Fatal("replacement did not reach requested raw slot")
	}
	otherStart, _, _ := SlotBounds(1)
	if got[otherStart] != plain[otherStart] {
		t.Fatal("write changed a different slot")
	}
	if plain[start] == got[start] {
		t.Fatal("write unexpectedly mutated caller image")
	}
	if _, err := WriteSlot(plain, 0, Slot{Roster: []byte{1}, Metadata: make([]byte, MetadataSize)}); err == nil {
		t.Fatal("short roster unexpectedly accepted")
	}
}

func TestInspectChapterSlotPreservesFixedRosterAndOpaqueMetadata(t *testing.T) {
	plain := make([]byte, FileSize)
	start, _, err := SlotBounds(1)
	if err != nil {
		t.Fatal(err)
	}
	for record := 0; record < RosterUnits; record++ {
		for offset := 0; offset < UnitSize; offset++ {
			plain[start+record*UnitSize+offset] = byte(record*17 + offset)
		}
	}
	metadata := start + RosterSize
	plain[metadata] = 3
	plain[metadata+1] = 2
	binary.LittleEndian.PutUint32(plain[metadata+2:], 123456)
	copy(plain[metadata+6:], []byte{0xa1, 0xa2, 0xa3, 0xa4})
	plain[metadata+MetadataSize-1] = 0xef

	got, err := InspectChapterSlot(plain, 1)
	if err != nil {
		t.Fatal(err)
	}
	if got.Slot != 1 ||
		got.Verified != (VerifiedMetadata{
			Chapter: 3, RosterCount: 2, Currency: 123456,
			HUDGateA: 0xa1, Raw53AF9: 0xa2, Raw51E61: 0xa3, Raw51E62: 0xa4,
		}) {
		t.Fatalf("snapshot header=%#v", got)
	}
	if got.Metadata[6] != 0xa1 || got.Metadata[MetadataSize-1] != 0xef {
		t.Fatal("opaque metadata was not preserved")
	}
	if got.Records[31].Raw[49] != byte((31*17+49)%256) {
		t.Fatal("fixed-capacity roster tail was not preserved")
	}
	active := got.ActiveRecords()
	if len(active) != 2 || active[1].Raw[8] != byte(17+8) {
		t.Fatalf("active records=%#v", active)
	}
	active[0].Raw[0] ^= 0xff
	if active[0].Raw[0] == got.Records[0].Raw[0] {
		t.Fatal("active records unexpectedly alias the snapshot")
	}
}

func TestInspectChapterSlotFailsClosedForEmptyAndOversizedCount(t *testing.T) {
	plain := make([]byte, FileSize)
	start, _, err := SlotBounds(0)
	if err != nil {
		t.Fatal(err)
	}
	metadata := start + RosterSize
	plain[metadata] = 0xff
	if _, err := InspectChapterSlot(plain, 0); !errors.Is(err, ErrEmptyChapterSlot) {
		t.Fatalf("empty slot error=%v", err)
	}
	plain[metadata] = 1
	plain[metadata+1] = RosterUnits + 1
	if _, err := InspectChapterSlot(plain, 0); err == nil {
		t.Fatal("oversized roster count unexpectedly accepted")
	}
}

func TestPersistentRecordViewUsesProvenOffsetsAndSignedWords(t *testing.T) {
	var record PersistentRecord
	record.Raw[5] = 0x81
	record.Raw[6] = 2
	record.Raw[7] = 0x34
	record.Raw[8] = 9
	for slot := 0; slot < 8; slot++ {
		record.Raw[0x0a+slot*2] = byte(0x40 + slot)
		record.Raw[0x0b+slot*2] = byte(0x20 + slot)
	}
	copy(record.Raw[0x1a:0x1f], []byte{1, 2, 3, 4, 5})
	record.Raw[0x1f] = 6
	record.Raw[0x20] = 7
	record.Raw[0x21] = 8
	copy(record.Raw[0x22:0x28], []byte{9, 10, 11, 12, 13, 14})
	record.Raw[0x3b] = 15
	record.Raw[0x3c] = 16
	for offset, value := range map[int]int16{
		0x37: -17,
		0x39: 18,
		0x3e: -19,
		0x40: 20,
		0x42: 21,
		0x44: 22,
		0x46: 23,
		0x48: 24,
		0x4a: 25,
		0x4c: -26,
		0x4e: 27,
	} {
		binary.LittleEndian.PutUint16(record.Raw[offset:], uint16(value))
	}

	got := record.View()
	if got.RawByte5 != 0x81 || got.RawCamp != 2 ||
		got.RawPresentationKey != 0x34 || got.RawIdentity != 9 ||
		got.Inventory[7] != (PersistentInventoryCell{Flags: 0x47, ItemID: 0x27}) ||
		got.CommandMask != ([5]byte{1, 2, 3, 4, 5}) ||
		got.Race != 6 || got.Class != 7 || got.Level != 8 ||
		got.Transient != ([6]byte{9, 10, 11, 12, 13, 14}) ||
		got.BaseAP != -17 || got.BaseDP != 18 ||
		got.Movement != 15 || got.Experience != 16 ||
		got.DX != -19 || got.HP != 20 || got.MaxHP != 21 ||
		got.MP != 22 || got.MaxMP != 23 || got.AP != 24 ||
		got.DP != 25 || got.HIT != -26 || got.EV != 27 {
		t.Fatalf("persistent view=%#v", got)
	}
	if record.Raw[0x37] == 0 {
		t.Fatal("view unexpectedly mutated the raw record")
	}
}

func TestInspectCurrentSnapshotUsesIDA10010Offsets(t *testing.T) {
	plain := make([]byte, FileSize)
	plain[CurrentRawBattleStateOffset] = 0x11
	plain[CurrentRawBattleStateOffset+CurrentRawBattleStateSize-1] = 0x22
	plain[CurrentRaw30A3Offset] = 0x33
	plain[CurrentRaw30A3Offset+CurrentRaw30A3Size-1] = 0x44
	header := plain[CurrentRuntimeHeaderOffset : CurrentRuntimeHeaderOffset+CurrentRuntimeHeaderSize]
	copy(header, []byte{
		3, 2, 7,
		1, 13, 8, 17, 7, 4,
		1,
		0x78, 0x56, 0x34, 0x12,
		0xaa, 1, 0xbb, 0xcc,
	})
	plain[CurrentPersistentRosterOffset+8] = 9
	plain[CurrentRuntimeRosterOffset+8] = 4
	plain[CurrentRuntimeRosterOffset+UnitSize+8] = 30

	got, err := InspectCurrentSnapshot(plain)
	if err != nil {
		t.Fatal(err)
	}
	if got.Header.TurnCounter != 3 || got.Header.RuntimeCount != 2 ||
		got.Header.PersistentCount != 1 || got.Header.Chapter != 7 ||
		got.Header.Currency != 0x12345678 || got.Header.HUDGateA != 1 {
		t.Fatalf("current header=%#v", got.Header)
	}
	if active := got.ActivePersistentRecords(); len(active) != 1 ||
		active[0].View().RawIdentity != 9 {
		t.Fatalf("current persistent records=%#v", active)
	}
	if len(got.RuntimeRecords) != 2 ||
		got.RuntimeRecords[0].View().RawIdentity != 4 ||
		got.RuntimeRecords[1].View().RawIdentity != 30 {
		t.Fatalf("current runtime records=%#v", got.RuntimeRecords)
	}
	if got.RawBattleState[0] != 0x11 ||
		got.RawBattleState[len(got.RawBattleState)-1] != 0x22 ||
		got.Raw30A3[0] != 0x33 ||
		got.Raw30A3[len(got.Raw30A3)-1] != 0x44 {
		t.Fatalf(
			"current raw regions battle=%#x/%#x block30a3=%#x/%#x",
			got.RawBattleState[0],
			got.RawBattleState[len(got.RawBattleState)-1],
			got.Raw30A3[0],
			got.Raw30A3[len(got.Raw30A3)-1],
		)
	}
	plain[CurrentRawBattleStateOffset] = 0
	plain[CurrentRaw30A3Offset] = 0
	if got.RawBattleState[0] != 0x11 || got.Raw30A3[0] != 0x33 {
		t.Fatal("current snapshot raw regions alias caller plaintext")
	}
}

func TestInspectCurrentSnapshotRejectsImpossibleCounts(t *testing.T) {
	plain := make([]byte, FileSize)
	plain[CurrentRuntimeHeaderOffset+1] = RosterUnits*3 + 1
	if _, err := InspectCurrentSnapshot(plain); err == nil {
		t.Fatal("oversized runtime count unexpectedly accepted")
	}
	plain[CurrentRuntimeHeaderOffset+1] = 0
	plain[CurrentRuntimeHeaderOffset+9] = RosterUnits + 1
	if _, err := InspectCurrentSnapshot(plain); err == nil {
		t.Fatal("oversized persistent count unexpectedly accepted")
	}
}
