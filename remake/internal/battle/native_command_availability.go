package battle

// NativeCommandAvailable is the narrow selector gate recovered from
// 0x159fa: the command bit must exist in unit+0x1a..+0x1e, its verified
// 0x4e516 record must be present, and record+5 (MP cost) must be <= runtime
// unit+0x44. It deliberately does not include the action-direction +0x27
// gate, target geometry, or any command/status name.
func NativeCommandAvailable(unit *Unit, book []NativeCommandRecord, commandID int) bool {
	if unit == nil || commandID < 0 || commandID >= 36 || len(book) != 36 || book[commandID].ID != commandID {
		return false
	}
	if unit.NativeCommandMask[commandID/8]&(1<<uint(commandID%8)) == 0 {
		return false
	}
	return book[commandID].MPCost >= 0 && book[commandID].MPCost <= unit.MP
}

// NativeAvailableCommandIDs returns only IDs with a closed command record and
// sufficient current MP. Unknown physical bits 36..39 are omitted rather
// than promoted to executable commands.
func NativeAvailableCommandIDs(unit *Unit, book []NativeCommandRecord) []int {
	if unit == nil || len(book) != 36 {
		return nil
	}
	ids := make([]int, 0, 36)
	for id := 0; id < 36; id++ {
		if NativeCommandAvailable(unit, book, id) {
			ids = append(ids, id)
		}
	}
	return ids
}

// NativeAvailableAICommandIDs adds the 0x1598a dispatcher gate to the
// bounded command scan: raw unit+0x27 must be zero before command bytes are
// enumerated. Unknown physical IDs 36..39 remain omitted.
func NativeAvailableAICommandIDs(unit *Unit, book []NativeCommandRecord) []int {
	if unit == nil || unit.NativeTransient[5] != 0 {
		return nil
	}
	return NativeAvailableCommandIDs(unit, book)
}
