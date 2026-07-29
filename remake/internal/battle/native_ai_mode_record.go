package battle

import "fmt"

// NativeAIModeRecordForUnit materializes only the raw fields consumed by
// 0x13a9f / fdother.PlanNativeUnitMode. Every source must have explicit
// provenance; normalized Camp, class, AI flags, or scenario strings are not
// substitutes for the constructor bytes.
func NativeAIModeRecordForUnit(unit *Unit) ([]byte, error) {
	if unit == nil ||
		!unit.HasNativeRecordByte5 ||
		!unit.HasNativeRecordByte34 ||
		!unit.HasNativeRecordByte35 ||
		!unit.HasNativeRecordByte36 ||
		!unit.HasNativeRecordRace {
		return nil, fmt.Errorf("native AI mode record lacks raw provenance")
	}
	record := make([]byte, 0x3e)
	record[5] = unit.NativeRecordByte5
	record[0x34] = unit.NativeRecordByte34
	record[0x35] = unit.NativeRecordByte35
	record[0x36] = unit.NativeRecordByte36
	// 0x10fcb copies FDFIELD b2 to runtime +0x3d; the same source is already
	// preserved as NativeRecordRace by the constructor/export boundary.
	record[0x3d] = unit.NativeRecordRace
	return record, nil
}
