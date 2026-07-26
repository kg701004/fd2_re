package fdother

import "fmt"

// NativePreparationDispatchMatch is the raw result of one 0x1a813 table
// scan.  The table's overlapping byte layout is intentional: native computes
// base + 3*i, then reads offsets +3, +5, and +4.
type NativePreparationDispatchMatch struct {
	Slot          int
	EntryStart    int
	FunctionIndex byte
}

// FindNativePreparationDispatch scans the exact sixteen native candidates.
// It returns every match in source order; caller-owned function-table
// invocation is deliberately outside this data primitive.
func FindNativePreparationDispatch(table []byte, gate3, selector byte) ([]NativePreparationDispatchMatch, error) {
	const slots = 16
	const stride = 3
	const lastRead = 5
	need := (slots-1)*stride + lastRead + 1
	if len(table) < need {
		return nil, fmt.Errorf("fdother: preparation dispatch table has %d bytes, need at least %d", len(table), need)
	}
	matches := make([]NativePreparationDispatchMatch, 0)
	for slot := 0; slot < slots; slot++ {
		start := slot * stride
		if table[start+3] != gate3 || table[start+5] != selector {
			continue
		}
		matches = append(matches, NativePreparationDispatchMatch{
			Slot: slot, EntryStart: start, FunctionIndex: table[start+4],
		})
	}
	return matches, nil
}
