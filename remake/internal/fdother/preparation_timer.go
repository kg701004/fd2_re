package fdother

import "errors"

// NativePreparationTimerExpiry records one exact 0x1a941 transition.  The
// source offset is retained because the following native renderer uses
// counter-index-derived data; no status/effect name is inferred here.
type NativePreparationTimerExpiry struct {
	RecordIndex        int
	CounterIndex       int
	CounterOffset      int
	VisualSourceOffset int
}

// TickNativePreparationTimers performs the raw 0x1a941 scan in place over
// 0x50-byte records. It returns only counters that changed 1→0.
func TickNativePreparationTimers(records []byte, recordCount, selector int) ([]NativePreparationTimerExpiry, error) {
	if recordCount < 0 || selector < 0 || selector > 0xff {
		return nil, errors.New("fdother: invalid preparation timer arguments")
	}
	const recordSize = 0x50
	const counterBase = 0x22
	const counterCount = 6
	need := recordCount * recordSize
	if need < 0 || len(records) < need {
		return nil, errors.New("fdother: preparation timer records are truncated")
	}
	expired := make([]NativePreparationTimerExpiry, 0)
	for recordIndex := 0; recordIndex < recordCount; recordIndex++ {
		base := recordIndex * recordSize
		if int(records[base+6]) != selector || records[base+5]&1 != 0 {
			continue
		}
		for counterIndex := 0; counterIndex < counterCount; counterIndex++ {
			offset := base + counterBase + counterIndex
			if records[offset] == 0 {
				continue
			}
			records[offset]--
			if records[offset] == 0 {
				expired = append(expired, NativePreparationTimerExpiry{
					RecordIndex: recordIndex, CounterIndex: counterIndex,
					CounterOffset:      counterBase + counterIndex,
					VisualSourceOffset: 0x1e1 + counterIndex,
				})
			}
		}
	}
	return expired, nil
}
