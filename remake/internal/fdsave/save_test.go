package fdsave

import (
	"encoding/binary"
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
