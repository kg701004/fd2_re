package campaign

import (
	"fmt"
	"reflect"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/fdicon"
	"github.com/wicanr2/fd2_re/remake/internal/fdsave"
)

// MaterializeNativeContinueRuntimeUnits projects the complete saved 0x50-byte
// runtime roster into battle.Units without consulting FDFIELD constructor
// rows. The saved list order is authoritative. Raw +7 is consumed separately
// as the battle-figure selector and as the CONTINUE selector-cache rebuild key;
// raw +8 is promoted to persistent identity only for native camp 2.
//
// This adapter deliberately does not seed map timing, switch to interactive
// range mode, construct future FDFIELD groups, or start the battle driver.
func MaterializeNativeContinueRuntimeUnits(
	state *battle.State,
	input fdsave.ContinueRuntimeInput,
	catalog *NativeCharacterCatalog,
) error {
	if state == nil {
		return fmt.Errorf("native CONTINUE runtime units: nil battle state")
	}
	if !input.ValidatedForRuntimeBridge() {
		return fmt.Errorf("native CONTINUE runtime units: input did not pass preflight")
	}
	if err := catalog.validate(); err != nil {
		return fmt.Errorf("native CONTINUE runtime units: %w", err)
	}
	if !state.HasNativeFieldControlState ||
		len(state.NativeRuntimeRecords) != len(input.RuntimeRecords) {
		return fmt.Errorf("native CONTINUE runtime units: field boundary is incomplete")
	}
	for index, record := range input.RuntimeRecords {
		want := battle.NativeRuntimeRecordState{
			SelectorKey: record.SelectorKey, SelectorSlot: record.SelectorSlot,
		}
		copy(want.Raw[:], record.Raw.Raw[:])
		if !reflect.DeepEqual(state.NativeRuntimeRecords[index], want) {
			return fmt.Errorf(
				"native CONTINUE runtime units: field record %d mismatch", index,
			)
		}
	}

	units := make([]*battle.Unit, len(input.RuntimeRecords))
	for index, record := range input.RuntimeRecords {
		unit, err := materializeNativeContinueRuntimeUnit(
			record, input.Context.FieldWidth, input.Context.FieldHeight, catalog,
		)
		if err != nil {
			return fmt.Errorf(
				"native CONTINUE runtime units: record %d: %w", index, err,
			)
		}
		units[index] = unit
	}

	cache := &fdicon.NativeSelectorCache{}
	if err := battle.MaterializeNativeMapSelectorSlots(units, cache); err != nil {
		return fmt.Errorf("native CONTINUE runtime units: %w", err)
	}
	for index, record := range input.RuntimeRecords {
		if units[index].MapSelectorSlot != int(record.SelectorSlot) {
			return fmt.Errorf(
				"native CONTINUE runtime units: record %d selector order mismatch",
				index,
			)
		}
		raw := record.Raw.Raw
		units[index].NativeMapPresentation = battle.NativeMapPresentationState{
			X: raw[0], Y: raw[1], Pose: raw[3], Motion: raw[4],
		}
		units[index].HasNativeMapPresentation = true
		units[index].Dir = int(raw[3])
		units[index].OffX, units[index].OffY = 0, 0
	}

	candidate := *state
	candidate.Units = units
	candidate.NativeMapSelectorCache = cache
	candidate.NativeMapSelectorError = nil
	candidate.HasNativeRuntimeUnitProjection = true
	*state = candidate
	return nil
}

func materializeNativeContinueRuntimeUnit(
	record fdsave.ContinueRuntimeRecord,
	fieldWidth, fieldHeight int,
	catalog *NativeCharacterCatalog,
) (*battle.Unit, error) {
	raw := record.Raw.Raw
	view := record.Raw.View()
	var camp battle.Camp
	switch view.RawCamp {
	case 0:
		camp = battle.Enemy
	case 1:
		camp = battle.Ally
	case 2:
		camp = battle.Own
	default:
		return nil, fmt.Errorf("raw camp %d is outside 0..2", view.RawCamp)
	}
	if int(view.Class) >= len(catalog.classNames) {
		return nil, fmt.Errorf("class %d outside catalog", view.Class)
	}
	active := raw[5]&1 == 0
	if active && (int(raw[0]) >= fieldWidth || int(raw[1]) >= fieldHeight ||
		raw[3] > 3 || raw[4] > 6) {
		return nil, fmt.Errorf("active map presentation is outside field")
	}

	unit := &battle.Unit{
		Camp:                  camp,
		Name:                  catalog.classNames[view.Class],
		ClsName:               catalog.classNames[view.Class],
		ClassID:               int(view.Class),
		Lv:                    int(view.Level),
		HP:                    int(view.HP),
		MaxHP:                 int(view.MaxHP),
		MP:                    int(view.MP),
		MaxMP:                 int(view.MaxMP),
		AP:                    int(view.AP),
		DP:                    int(view.DP),
		HIT:                   int(view.HIT),
		EV:                    int(view.EV),
		MV:                    int(view.Movement),
		X:                     int(raw[0]),
		Y:                     int(raw[1]),
		Dir:                   int(raw[3]),
		Acted:                 raw[5]&0x80 != 0,
		OnField:               active,
		MapSelectorKey:        int(record.SelectorKey),
		HasMapSelectorKey:     true,
		BattleFig:             int(raw[7]),
		HasBattleFig:          true,
		NativeRecordByte8:     raw[8],
		HasNativeRecordByte8:  true,
		NativeRecordRace:      view.Race,
		HasNativeRecordRace:   true,
		NativeRecordClass:     view.Class,
		HasNativeRecordClass:  true,
		NativeCommandMask:     view.CommandMask,
		NativeTransient:       view.Transient,
		NativeRecordByte5:     view.RawByte5,
		HasNativeRecordByte5:  true,
		NativeRecordByte6:     view.RawCamp,
		HasNativeRecordByte6:  true,
		NativeRecordByte34:    raw[0x34],
		HasNativeRecordByte34: true,
		NativeRecordByte35:    raw[0x35],
		HasNativeRecordByte35: true,
		NativeRecordByte36:    raw[0x36],
		HasNativeRecordByte36: true,
		NativeRecordByte3D:    raw[0x3d],
		HasNativeRecordByte3D: true,
		NativeRecordDeathEffect: [3]byte{
			raw[0x31], raw[0x32], raw[0x33],
		},
		HasNativeRecordDeathEffect: true,
		NativeRecordWord42:         uint16(raw[0x42]) | uint16(raw[0x43])<<8,
		HasNativeRecordWord42:      true,
		NativeRecordWord46:         uint16(raw[0x46]) | uint16(raw[0x47])<<8,
		HasNativeRecordWord46:      true,
		BaseAP:                     int(view.BaseAP),
		BaseDP:                     int(view.BaseDP),
		BaseHIT:                    int(view.DX),
		BaseEV:                     int(view.DX),
		BaseMV:                     int(view.Movement),
		EquipmentBaseSet:           true,
		DX:                         int(view.DX),
		Exp:                        float64(view.Experience),
		InventorySlots:             make([]int, len(view.Inventory)),
		NativeInventoryFlags:       make([]int, len(view.Inventory)),
		NativeMapPresentation: battle.NativeMapPresentationState{
			X: raw[0], Y: raw[1], Pose: raw[3], Motion: raw[4],
		},
		HasNativeMapPresentation: true,
	}
	for slot, cell := range view.Inventory {
		unit.InventorySlots[slot] = int(cell.ItemID)
		unit.NativeInventoryFlags[slot] = int(cell.Flags)
		if int8(cell.Flags) < 0 {
			continue
		}
		unit.Inventory = append(unit.Inventory, int(cell.ItemID))
		unit.Equipped = append(unit.Equipped, cell.Flags&0x40 != 0)
	}
	if camp == battle.Own {
		identity := int(raw[8])
		if identity >= len(catalog.identityNames) {
			return nil, fmt.Errorf("own identity %d outside catalog", identity)
		}
		unit.NativeIdentity = identity
		unit.HasNativeIdentity = true
		unit.Name = catalog.identityNames[identity]
	}
	return unit, nil
}
