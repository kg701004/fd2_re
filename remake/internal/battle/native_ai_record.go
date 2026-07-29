package battle

import "fmt"

// NativeAIScoringRecords materializes the raw runtime fields consumed across
// 0x1598a, 0x15b77 and their phase admission. It deliberately requires an
// already-materialized native map position and every optional record byte
// used by those paths; normalized X/Y, Acted, Camp or status fields are never
// substituted. The returned buffer is a detached snapshot.
func NativeAIScoringRecords(units []*Unit) ([]byte, error) {
	records := make([]byte, 0, len(units)*nativeRecordSize)
	for index, unit := range units {
		if unit == nil || !unit.HasNativeMapPresentation ||
			!unit.HasBattleFig ||
			!unit.HasNativeRecordByte5 ||
			!unit.HasNativeRecordByte34 ||
			!unit.HasNativeRecordByte35 ||
			!unit.HasNativeRecordByte36 {
			return nil, fmt.Errorf("native AI record: unit %d lacks raw provenance", index)
		}
		record, err := NativeItemPanelRecordForUnit(unit)
		if err != nil {
			return nil, fmt.Errorf("native AI record: unit %d: %w", index, err)
		}
		presentation := unit.NativeMapPresentation
		record[0] = presentation.X
		record[1] = presentation.Y
		record[3] = presentation.Pose
		record[4] = presentation.Motion
		record[5] = unit.NativeRecordByte5
		record[0x34] = unit.NativeRecordByte34
		record[0x35] = unit.NativeRecordByte35
		record[0x36] = unit.NativeRecordByte36
		records = append(records, record...)
	}
	return records, nil
}
