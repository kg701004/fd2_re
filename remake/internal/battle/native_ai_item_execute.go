package battle

import "encoding/binary"

// nativeItemExecutionRecords/nativeItemExecutionSync mirror
// cmd/fd2/native_item_panel_ui.go's nativeItemRuntimeRecords/
// syncNativeItemRuntimeRecord exactly (the flat 80-byte-per-unit item-panel
// record format used by NativeItemPanelRecordForUnit and every
// ApplyNativeItem* mutator -- distinct from nativeRecordSize's AI-scoring
// record layout), duplicated here rather than exported from cmd/fd2 so the
// battle package stays free of a reverse dependency on the game binary.
func nativeItemExecutionRecords(units []*Unit) ([]byte, error) {
	records := make([]byte, 0, len(units)*80)
	for _, unit := range units {
		record, err := NativeItemPanelRecordForUnit(unit)
		if err != nil {
			return nil, err
		}
		if unit.X < 0 || unit.X > 0xff || unit.Y < 0 || unit.Y > 0xff || !unit.HasNativeRecordByte5 {
			return nil, errNativeItemExecutionProvenance
		}
		record[0], record[1], record[5] = byte(unit.X), byte(unit.Y), unit.NativeRecordByte5
		records = append(records, record...)
	}
	return records, nil
}

func nativeItemExecutionSync(unit *Unit, record []byte) {
	unit.HP = int(int16(binary.LittleEndian.Uint16(record[0x40:0x42])))
	unit.MP = int(int16(binary.LittleEndian.Uint16(record[0x44:0x46])))
	unit.SetMapPlacement(int(record[0]), int(record[1]), unit.Dir)
	unit.AP = int(int16(binary.LittleEndian.Uint16(record[0x48:0x4a])))
	unit.DP = int(int16(binary.LittleEndian.Uint16(record[0x4a:0x4c])))
	unit.HIT = int(int16(binary.LittleEndian.Uint16(record[0x4c:0x4e])))
	unit.EV = int(int16(binary.LittleEndian.Uint16(record[0x4e:0x50])))
	copy(unit.NativeTransient[:], record[0x22:0x28])
	unit.InventorySlots = make([]int, nativeInventoryCells)
	unit.NativeInventoryFlags = make([]int, nativeInventoryCells)
	unit.Inventory = unit.Inventory[:0]
	unit.Equipped = unit.Equipped[:0]
	for slot := 0; slot < nativeInventoryCells; slot++ {
		flag, item := int(record[0x0a+slot*2]), int(record[0x0b+slot*2])
		unit.NativeInventoryFlags[slot], unit.InventorySlots[slot] = flag, item
		if flag&0x80 == 0 {
			unit.Inventory = append(unit.Inventory, item)
			unit.Equipped = append(unit.Equipped, flag&0x40 != 0)
		}
	}
}

var errNativeItemExecutionProvenance = errNativeAIItemExecution("native item execution: unit lacks raw coordinate/activity provenance")

type errNativeAIItemExecution string

func (e errNativeAIItemExecution) Error() string { return string(e) }

// ApplyNativeAIItemCommand executes one AI-selected item command (chosen by
// ScoreNativeAI1567E: InventorySlot/ItemID/X/Y) against a resolved target
// unit. It is a direct, UI-decoupled transcription of
// cmd/fd2/native_item_panel_ui.go's applyNativeTargetItem -- same
// RouteForType cascade, same records/sync bookkeeping, same RNG threading --
// with every g.sel/g.nativeItemTargeting/g.curX,Y player-cursor reference
// replaced by explicit parameters, so nativeAIThreeScorePlan's item winner
// can eventually execute instead of always deferring to legacy (see
// docs/knowledge-base/11-enemy-ai.md's 2026-08-15 note on this gap).
//
// Relocation-type items (native item type 23) are deliberately unsupported
// here: the original's relocation effect is a second interactive
// destination-picking step with its own legality scan
// (NativeRelocationDestinationAllowed over every board cell), which has no
// AI-side target-selection counterpart yet. ok=false in that case, matching
// every other fail-closed contract in this package -- the caller must not
// treat this as an error, just as "this AI item command has no execution
// path yet."
func (s *State) ApplyNativeAIItemCommand(
	actor, confirmed *Unit,
	itemID, rawSlot int,
	itemRows []byte,
	rngState uint16,
) (applied bool, nextRNG uint16, err error) {
	if s == nil || actor == nil || confirmed == nil {
		return false, rngState, nil
	}
	rowOffset, err := NativeItemEffectRowOffset(itemID)
	if err != nil || rowOffset+NativeItemEffectRowSize > len(itemRows) {
		return false, rngState, errNativeAIItemExecution("native AI item row is unavailable")
	}
	row := itemRows[rowOffset : rowOffset+NativeItemEffectRowSize]
	plan, err := NativeItemTargetPlanFromRow(row)
	if err != nil {
		return false, rngState, err
	}
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return false, rngState, err
	}
	targets, err := NativeItemEffectTargets(s.W, s.H, actor, confirmed, plan, flags, s.Units)
	if err != nil || len(targets) == 0 {
		return false, rngState, nil
	}
	sourceUnit := -1
	targetIndices := make([]byte, len(targets))
	for index, unit := range s.Units {
		if unit == actor {
			sourceUnit = index
		}
		for targetIndex, target := range targets {
			if unit == target {
				targetIndices[targetIndex] = byte(index)
			}
		}
	}
	if sourceUnit < 0 {
		return false, rngState, errNativeAIItemExecution("native AI item source is absent from runtime roster")
	}
	records, err := nativeItemExecutionRecords(s.Units)
	if err != nil {
		return false, rngState, err
	}
	amount := binary.LittleEndian.Uint16(row[0x0e:0x10])
	next := rngState
	if route, ok := NativeItemHPRestoreRouteForType(row[0x0d], amount); ok {
		result, e := ApplyNativeItemHPRestore(records, targetIndices, route, rngState, sourceUnit, rawSlot)
		if e != nil {
			return false, rngState, e
		}
		next = result.RNGState
	} else if route, ok := NativeItemMPRestoreRouteForType(row[0x0d], amount); ok {
		result, e := ApplyNativeItemMPRestore(records, targetIndices, route, rngState, sourceUnit, rawSlot)
		if e != nil {
			return false, rngState, e
		}
		next = result.RNGState
	} else if route, ok := NativeItemMarkerClearRestoreRouteForType(row[0x0d]); ok {
		_, state, _, e := ApplyNativeItemMarkerClearRestore(records, targetIndices, route, rngState, sourceUnit, rawSlot)
		if e != nil {
			return false, rngState, e
		}
		next = state
	} else if route, ok := NativeItemHITEVStepRouteForType(row[0x0d]); ok {
		_, state, _, e := ApplyNativeItemHITEVStep(records, targetIndices, route, rngState)
		if e != nil {
			return false, rngState, e
		}
		next = state
	} else if route, ok := NativeItemAPDPStepRouteForType(row[0x0d]); ok {
		_, state, _, e := ApplyNativeItemAPDPStep(records, targetIndices, route, rngState)
		if e != nil {
			return false, rngState, e
		}
		next = state
	} else if route, ok := NativeItemMarkerApplicationRouteForType(row[0x0d]); ok {
		_, state, _, e := ApplyNativeItemMarkerApplication(records, targetIndices, route, rngState)
		if e != nil {
			return false, rngState, e
		}
		next = state
	} else if route, ok := NativeItemCommandDamageRouteForType(row[0x0d], amount); ok {
		_, state, e := ApplyNativeItemCommandDamage(targets, route, s.NativeCommandBook, s.NativeCommandResistances, rngState)
		if e != nil {
			return false, rngState, e
		}
		next = state
		for index, unit := range s.Units {
			binary.LittleEndian.PutUint16(records[index*80+0x40:index*80+0x42], uint16(int16(unit.HP)))
		}
	} else {
		// Relocation (type 23) or an unrecognised type: no AI execution path.
		return false, rngState, nil
	}
	for index, unit := range s.Units {
		nativeItemExecutionSync(unit, records[index*80:(index+1)*80])
	}
	actor.NativeRecordByte5 |= 0x80
	actor.HasNativeRecordByte5 = true
	return true, next, nil
}
