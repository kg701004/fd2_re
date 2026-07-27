package battle

import (
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

type NativeRawApplicationResult struct {
	TargetIndex int
	Applied     bool
	Damage      NativeRawDamageResult
	Marker      byte
}

// ApplyNativeRawApplication reproduces the mutation/gate portion of 0x22d1b.
// A target is eligible only when its marker byte is zero, class byte +0x20 is
// not 0x19/0x1a, and the first RNG remainder mod 100 is below 50. Success
// calls 0x1c81f with base amount 10 (which advances RNG again and rolls
// amount*0.9 + RNG*amount/1000), advances RNG a third time, writes marker
// (RNG%4)+2 at markerOffset, and adds 8*record+0x21 to the accumulator.
// Presentation and marker/status names remain outside this adapter.
func ApplyNativeRawApplication(records []byte, targetIndices []byte, markerOffset int, rngState uint16) ([]NativeRawApplicationResult, uint16, int, error) {
	if markerOffset < 0 || markerOffset >= nativeRecordSize {
		return nil, rngState, 0, fmt.Errorf("native application marker offset %#x is out of bounds", markerOffset)
	}
	for _, rawIndex := range targetIndices {
		if int(rawIndex) >= len(records)/nativeRecordSize {
			return nil, rngState, 0, recordBoundsError(int(rawIndex))
		}
	}
	results := make([]NativeRawApplicationResult, 0, len(targetIndices))
	total := 0
	for _, rawIndex := range targetIndices {
		index := int(rawIndex)
		record := records[index*nativeRecordSize:]
		result := NativeRawApplicationResult{TargetIndex: index}
		if record[markerOffset] != 0 || record[0x20] == 0x19 || record[0x20] == 0x1a {
			results = append(results, result)
			continue
		}
		gateState := fdother.NativeRNGStep(rngState)
		if gateState%100 >= 50 {
			rngState = gateState
			results = append(results, result)
			continue
		}
		damage, err := ApplyNativeRawHPDamage(records, index, 10, gateState)
		if err != nil {
			return nil, rngState, 0, err
		}
		rngState = fdother.NativeRNGStep(damage.RNGState)
		marker := byte(rngState%4 + 2)
		record[markerOffset] = marker
		total += 8 * int(record[0x21])
		result.Applied, result.Damage, result.Marker = true, damage, marker
		results = append(results, result)
	}
	return results, rngState, total, nil
}
