package main

import (
	"fmt"

	"github.com/wicanr2/fd2_re/remake/internal/battle"
	"github.com/wicanr2/fd2_re/remake/internal/campaign"
)

// materializeShotPartyFromBinding is a screenshot-only bridge from an
// chosen compiled LOADCH party contract to the same typed persistent roster
// consumed by production town/shop UI. It deliberately requires the binding
// to provide both PartyScenario and PartyOrder; source row order is not a
// substitute for the binding's recorded JOIN order. This hook does not
// independently re-prove the binding's JOIN source addresses.
func (g *Game) materializeShotPartyFromBinding(path string) error {
	if g.shotPath == "" || path == "" {
		return fmt.Errorf("shot party binding requires screenshot mode and a path")
	}
	beats, issues, err := campaign.CompileHandlerBinding(assetPath(path))
	if err != nil {
		return err
	}
	if len(issues) != 0 {
		return fmt.Errorf("shot party binding has %d compile issues", len(issues))
	}
	var source *campaign.LoadCHState
	for _, beat := range beats {
		if beat.LoadCH == nil || beat.LoadCH.PartyScenario == "" ||
			len(beat.LoadCH.PartyOrder) == 0 {
			continue
		}
		if source != nil {
			return fmt.Errorf("shot party binding has multiple party LOADCH states")
		}
		source = beat.LoadCH
	}
	if source == nil {
		return fmt.Errorf("shot party binding has no complete party LOADCH state")
	}
	scenario, err := battle.LoadScenario(assetPath(source.PartyScenario))
	if err != nil {
		return err
	}
	if err := reorderScenarioParty(scenario, source.PartyOrder); err != nil {
		return err
	}
	units := scenario.PartyUnits(nil)
	if len(units) != len(source.PartyOrder) {
		return fmt.Errorf(
			"shot party materialized %d units for %d JOIN entries",
			len(units), len(source.PartyOrder),
		)
	}
	state := &battle.State{Units: units}
	g.initializeEquipmentBases(state)

	members := make(map[int]bool, len(units))
	roster := make(map[int]battle.Unit, len(units))
	order := append([]int(nil), source.PartyOrder...)
	for i, unit := range units {
		id := order[i]
		if unit == nil || unit.Fig != id || !unit.HasNativeIdentity ||
			unit.NativeIdentity != id || !unit.HasMapSelectorKey ||
			len(unit.InventorySlots) != 8 ||
			len(unit.NativeInventoryFlags) != 8 ||
			!unit.HasNativeRecordByte6 || !unit.HasNativeRecordRace ||
			!unit.HasNativeRecordClass || !unit.EquipmentBaseSet {
			return fmt.Errorf("shot party unit %d lacks native recipient provenance", id)
		}
		if _, exists := roster[id]; exists {
			return fmt.Errorf("shot party duplicate JOIN identity %d", id)
		}
		members[id] = true
		roster[id] = *unit
	}
	g.partyMembers = members
	g.partyJoinOrder = order
	g.partyRoster = roster
	return nil
}
