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
	meta, err := ReadVerifiedMetadata(plain, 2)
	if err != nil || meta.Chapter != 0xff || meta.RosterCount != 7 || meta.Currency != 0x12345678 {
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
	plain[metadata+6] = 0xa1
	plain[metadata+MetadataSize-1] = 0xef

	got, err := InspectChapterSlot(plain, 1)
	if err != nil {
		t.Fatal(err)
	}
	if got.Slot != 1 ||
		got.Verified != (VerifiedMetadata{Chapter: 3, RosterCount: 2, Currency: 123456}) {
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
