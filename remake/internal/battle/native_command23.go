package battle

import (
	"fmt"
	"math/rand"
)

// NativeCommand23Result is the state result of player-dispatched native
// command 23 (傳送術/relocation, doc13 §5).
type NativeCommand23Result struct {
	Target       *Unit
	FromX, FromY int
	ToX, ToY     int
	Relocated    bool
}

// ExecuteNativeCommand23 is a state-only slice of 0x2218A: record-23 MP
// debit, then relocate the selected unit to an explicitly supplied
// destination cell, followed by the [0x53EC8] experience credit.
//
// The real handler's two 0x22253 calls are a framebuffer exit/enter
// animation pair around the coordinate write (0xff/0xff placeholder, then
// the confirmed cursor globals -- doc13 §5), with no further state effect;
// this executor accepts the destination directly from the caller instead of
// driving that renderer, because the dedicated native map-cursor picker for
// ID23 does not exist yet in this engine (doc13's "engine integration" note:
// "legality/camera/render/UI 仍未接"). Once that picker is built, it only
// needs to supply destX/destY here -- no further signature change.
//
// Legality is deliberately simplified to in-bounds + unoccupied, not the
// exact raw-byte NativeRelocationDestinationAllowed movement-cost/table
// pipeline (that function operates on raw []byte unit records plus terrain
// cost rows that a *Unit-level caller does not have on hand here) -- see
// 13-battle-menu-system.md's 2026-08-20 note for the honest scoping.
func (s *State) ExecuteNativeCommand23(actor, target *Unit, destX, destY int, rng *rand.Rand) (NativeCommand23Result, error) {
	const commandID = 23
	if s == nil || rng == nil || actor == nil || target == nil {
		return NativeCommand23Result{}, fmt.Errorf("missing native command 23 state/actor/target/rng")
	}
	if len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[commandID].ID != commandID {
		return NativeCommand23Result{}, fmt.Errorf("native command 23 record unavailable")
	}
	if destX < 0 || destX >= s.W || destY < 0 || destY >= s.H {
		return NativeCommand23Result{}, fmt.Errorf("native command 23 destination out of bounds")
	}
	for _, u := range s.Units {
		if u == nil || u == target || !u.OnField || !u.Alive() {
			continue
		}
		if u.X == destX && u.Y == destY {
			return NativeCommand23Result{}, fmt.Errorf("native command 23 destination occupied")
		}
	}
	record := s.NativeCommandBook[commandID]
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return NativeCommand23Result{}, fmt.Errorf("native command 23 insufficient MP")
	}
	result := NativeCommand23Result{Target: target, FromX: target.X, FromY: target.Y, ToX: destX, ToY: destY}
	target.SetMapPlacement(destX, destY, target.Dir)
	result.Relocated = true
	// [0x53EC8] write point 0x2218a: levelFactor(target)*10, single target,
	// not a per-target loop (doc13 §5/§7, doc27 §5.1.A).
	s.awardNativeCommandExp(actor, []*Unit{target}, 10, rng)
	actor.Acted = true
	return result, nil
}
