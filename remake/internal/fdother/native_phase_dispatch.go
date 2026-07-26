package fdother

import "fmt"

// NativePhaseDispatchCandidate is the raw eligible record observed in the
// 0x1d80b phase loop.  Field names intentionally remain offsets: 0x13a9f
// assigns the event selector and invokes side effects, which are not closed
// by this data-only adapter.
type NativePhaseDispatchCandidate struct {
	UnitIndex   int
	SelectorArg byte
}

// FindNativePhaseDispatchCandidates reproduces the first 0x1d80b loop's
// eligibility gate.  Records are 0x50 bytes apart; count is the native global
// [0x53beb].  It does not invoke 0x13a9f or either function table.
func FindNativePhaseDispatchCandidates(records []byte, count int) ([]NativePhaseDispatchCandidate, error) {
	const stride = 0x50
	if count < 0 {
		return nil, fmt.Errorf("fdother: negative native phase count %d", count)
	}
	if count > 0 && len(records) < count*stride {
		return nil, fmt.Errorf("fdother: native phase records have %d bytes, need %d", len(records), count*stride)
	}
	candidates := make([]NativePhaseDispatchCandidate, 0)
	for unit := 0; unit < count; unit++ {
		record := records[unit*stride : (unit+1)*stride]
		if record[6] != 1 || record[5]&0x81 != 0 || record[0x26] != 0 {
			continue
		}
		candidates = append(candidates, NativePhaseDispatchCandidate{UnitIndex: unit, SelectorArg: record[6]})
	}
	return candidates, nil
}
