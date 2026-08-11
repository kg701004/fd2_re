package battle

import "testing"

func TestNativeCommandAvailabilityUsesRawBitAndMPCost(t *testing.T) {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
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
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: 0}
	}
	// bit 39 (byte4 bit7) is still genuinely unknown -- id36 (byte4 bit4,
	// mask 0x10) is now a real remake-only command (see
	// NativeCommandRecordCount's doc comment) and is deliberately excluded
	// from this mask so this test keeps proving true-unknown bits stay out.
	u := &Unit{MP: 0, NativeCommandMask: [5]byte{0, 0, 0, 0, 0x80}}
	if got := NativeAvailableCommandIDs(u, book); len(got) != 0 {
		t.Fatalf("unknown ID 39 should not be returned: %v", got)
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
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
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

func TestNativeAvailableAIScoredCommandIDsKeepsLowAndHighRawIndices(t *testing.T) {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	u := &Unit{MP: 4, NativeCommandMask: [5]byte{1 << 2, 0, 0, 1 << 4, 0}}
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: 0}
	}
	got := NativeAvailableAIScoredCommandIDs(u, book)
	if len(got) != 2 || got[0] != 2 || got[1] != 28 {
		t.Fatalf("raw AI scored commands = %#v, want [2 28]", got)
	}
}

func TestNativeAvailableAIScoredCommandIDsFailsClosedOnRaw27Gate(t *testing.T) {
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id, MPCost: 0}
	}
	u := &Unit{NativeTransient: [6]byte{0, 0, 0, 0, 0, 1}, NativeCommandMask: [5]byte{0xff, 0xff, 0xff, 0xff, 0xff}}
	if got := NativeAvailableAIScoredCommandIDs(u, book); got != nil {
		t.Fatalf("raw +0x27 gate must reject AI scored commands: %#v", got)
	}
}
