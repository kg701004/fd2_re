package battle

import "testing"

func TestNativeCommandAvailabilityUsesRawBitAndMPCost(t *testing.T) {
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: id}
	}
	u := &Unit{MP: 3, NativeCommandMask: [5]byte{0x0f}}
	for id := 0; id < 4; id++ {
		if !NativeCommandAvailable(u, book, id) {
			t.Fatalf("command %d unexpectedly unavailable", id)
		}
	}
	if NativeCommandAvailable(u, book, 4) {
		t.Fatal("command over current MP accepted")
	}
	u.NativeCommandMask[0] &^= 1 << 1
	if NativeCommandAvailable(u, book, 1) {
		t.Fatal("missing raw command bit accepted")
	}
}

func TestNativeAvailableCommandIDsOmitsUnknownPhysicalBits(t *testing.T) {
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: 0}
	}
	u := &Unit{MP: 0, NativeCommandMask: [5]byte{0, 0, 0, 0, 0x90}}
	if got := NativeAvailableCommandIDs(u, book); len(got) != 0 {
		t.Fatalf("unknown IDs 36/39 should not be returned: %v", got)
	}
	u.NativeCommandMask[4] = 1
	if got := NativeAvailableCommandIDs(u, book); len(got) != 1 || got[0] != 32 {
		t.Fatalf("closed ID32 missing from availability: %v", got)
	}
}

func TestNativeCommandAvailabilityFailsClosedOnMalformedBook(t *testing.T) {
	u := &Unit{MP: 99, NativeCommandMask: [5]byte{1}}
	if NativeCommandAvailable(u, nil, 0) || NativeAvailableCommandIDs(u, nil) != nil {
		t.Fatal("malformed command book did not fail closed")
	}
}

func TestNativeAvailableAICommandIDsAppliesRaw27Gate(t *testing.T) {
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: 0}
	}
	u := &Unit{MP: 1, NativeCommandMask: [5]byte{1, 0, 0, 0, 0}}
	if got := NativeAvailableAICommandIDs(u, book); len(got) != 1 || got[0] != 0 {
		t.Fatalf("ungated AI commands=%v", got)
	}
	u.NativeTransient[5] = 1
	if got := NativeAvailableAICommandIDs(u, book); got != nil {
		t.Fatalf("raw +0x27 gate ignored: %v", got)
	}
}

func TestNativeAvailableAISpellCommandIDsKeepsRawCommandIDs(t *testing.T) {
	book := make([]NativeCommandRecord, 36)
	u := &Unit{MP: 4, NativeCommandMask: [5]byte{0, 0, 0, 0x81, 0}}
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: 0}
	}
	got := NativeAvailableAISpellCommandIDs(u, book)
	if len(got) != 2 || got[0] != 24 || got[1] != 31 {
		t.Fatalf("raw AI spell commands = %#v, want [24 31]", got)
	}
	// The caller, not this raw adapter, owns command-0x10 conversion.
	if got[0]-0x10 != 8 || got[1]-0x10 != 15 {
		t.Fatalf("spell conversion check failed for %#v", got)
	}
}

func TestNativeAvailableAISpellCommandIDsFailsClosedOnRaw27Gate(t *testing.T) {
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: 0}
	}
	u := &Unit{NativeTransient: [6]byte{0, 0, 0, 0, 0, 1}, NativeCommandMask: [5]byte{0xff, 0xff, 0xff, 0xff, 0xff}}
	if got := NativeAvailableAISpellCommandIDs(u, book); got != nil {
		t.Fatalf("raw +0x27 gate must reject AI spell commands: %#v", got)
	}
}
