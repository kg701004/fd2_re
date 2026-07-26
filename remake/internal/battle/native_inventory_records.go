package battle

import "fmt"

// NativeInventoryRecords materializes only the proven inventory cells of a
// runtime roster. The surrounding 0x50-byte records stay zeroed because this
// adapter is intentionally scoped to 0x24b14/0x31860's +0x0a inventory ABI.
// It fails closed when any requested unit lacks the source slots/flags needed
// to reproduce the native prefix gate.
func NativeInventoryRecords(units []*Unit, count int) ([]byte, error) {
	if count < 0 || count > len(units) || count > 16 {
		return nil, fmt.Errorf("native inventory records: count %d outside 0..%d", count, minInt(len(units), 16))
	}
	records := make([]byte, count*nativeRecordSize)
	for i := 0; i < count; i++ {
		unit := units[i]
		if unit == nil || len(unit.InventorySlots) != nativeInventoryCells || len(unit.NativeInventoryFlags) != nativeInventoryCells {
			return nil, fmt.Errorf("native inventory records: unit %d lacks raw inventory provenance", i)
		}
		base := i * nativeRecordSize
		for slot := 0; slot < nativeInventoryCells; slot++ {
			item, flag := unit.InventorySlots[slot], unit.NativeInventoryFlags[slot]
			if item < 0 || item > 0xff || flag < 0 || flag > 0xff {
				return nil, fmt.Errorf("native inventory records: unit %d cell %d malformed", i, slot)
			}
			records[base+0x0a+slot*2] = byte(flag)
			records[base+0x0b+slot*2] = byte(item)
		}
	}
	return records, nil
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}
