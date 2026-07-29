package battle

import "fmt"

// NativeBattleResultCode205B4 reproduces the raw three-value result written by
// the 0x205b4 function, whose shared inner entry at 0x205be is called directly
// by chapter handlers. The numeric result is intentionally not renamed as a
// victory, defeat, or story transition: chapter handlers may overwrite the
// same global with the same values for other conditions.
//
// The native routine starts from code 2, changes it to 0 when any record whose
// raw +6 byte is zero also has raw +5 bit0 clear, then lets record zero's raw
// +5 bit0 override the result with code 1.
func NativeBattleResultCode205B4(records []byte, count int) (int, error) {
	if count <= 0 || count > 0x100 ||
		len(records) != count*nativeRecordSize {
		return 0, fmt.Errorf("native battle result 0x205b4 records are malformed")
	}

	result := 2
	for index := 0; index < count; index++ {
		record := records[index*nativeRecordSize:]
		if record[6] == 0 && record[5]&1 == 0 {
			result = 0
		}
	}
	if records[5]&1 != 0 {
		result = 1
	}
	return result, nil
}
