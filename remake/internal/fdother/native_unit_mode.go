package fdother

import "fmt"

// NativeUnitModePlan preserves the inputs selected by 0x13a9f before it
// dispatches to mode-specific callees.  The fields are deliberately raw: the
// callee effects and the meanings of +0x35/+0x36/+0x3d are not inferred.
type NativeUnitModePlan struct {
	UnitIndex  int
	CallerArg  byte
	Mode       byte
	RawArg35   byte
	RawArg36   byte
	RawCounter byte
}

// PlanNativeUnitMode reproduces 0x13a9f's admission gate and field reads.
// A rejected record returns (nil, nil); no mutation or callback is performed.
func PlanNativeUnitMode(record []byte, unitIndex int, callerArg byte) (*NativeUnitModePlan, error) {
	if len(record) < 0x3e {
		return nil, fmt.Errorf("fdother: native mode record has %d bytes, need at least 62", len(record))
	}
	if record[5]&5 != 0 {
		return nil, nil
	}
	return &NativeUnitModePlan{
		UnitIndex: unitIndex, CallerArg: callerArg,
		Mode: record[0x34] & 0x0f, RawArg35: record[0x35],
		RawArg36: record[0x36], RawCounter: record[0x3d],
	}, nil
}
