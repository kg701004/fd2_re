package battle

import "fmt"

// NativeInventoryFlagsFromSource reproduces the constructor writes at
// 0x10c50 for the eight FDFIELD inventory source bytes.  The first two cells
// are a special pair: a 0xff first byte collapses the second source item into
// cell 0 and reserves cell 1; otherwise both cells receive the equipped flag.
// Cells 2..7 are unequipped when their source item is present and reserved
// (bit 7 set) when it is 0xff.  The returned values are raw flag bytes, not
// normalized equipped booleans.
func NativeInventoryFlagsFromSource(source []int) ([]int, error) {
	if len(source) != nativeInventoryCells {
		return nil, fmt.Errorf("native inventory flags: source length=%d, want %d", len(source), nativeInventoryCells)
	}
	for i, value := range source {
		if value < 0 || value > 0xff {
			return nil, fmt.Errorf("native inventory flags: source[%d]=%d outside byte", i, value)
		}
	}
	flags := make([]int, nativeInventoryCells)
	flags[0] = nativeEquippedMask
	if source[0] == 0xff {
		flags[1] = 0x80
	} else {
		flags[1] = nativeEquippedMask
	}
	for i := 2; i < nativeInventoryCells; i++ {
		if source[i] == 0xff {
			flags[i] = 0x80
		}
	}
	return flags, nil
}

// NativeInventoryCompactEligible maps one compact item index to its runtime
// cell and applies the native signed-flag gate (flag byte signed >= 0). It rejects missing
// or misaligned provenance instead of inferring a flag from the item ID.
func NativeInventoryCompactEligible(flags, runtimeSlots []int, compactIndex int) (bool, error) {
	if len(flags) != nativeInventoryCells || len(runtimeSlots) != nativeInventoryCells {
		return false, fmt.Errorf("native inventory flags: need %d flags and slots", nativeInventoryCells)
	}
	if compactIndex < 0 {
		return false, fmt.Errorf("native inventory flags: negative compact index")
	}
	seen := 0
	for slot, item := range runtimeSlots {
		if item == 0xff {
			continue
		}
		if item < 0 || item > 0xff || flags[slot] < 0 || flags[slot] > 0xff {
			return false, fmt.Errorf("native inventory flags: malformed cell %d", slot)
		}
		if seen == compactIndex {
			return flags[slot]&0x80 == 0, nil
		}
		seen++
	}
	return false, fmt.Errorf("native inventory flags: compact index %d absent", compactIndex)
}
