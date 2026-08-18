package battle

// nativeAI14237Plan runs the same disassembly-confirmed native physical-
// attack decision as ApplyNativeAI14237PhysicalAttack below, but as a pure
// planning step for NextAIPlan (combat.go) instead of an immediate
// execution: NextAIPlan must not move or attack directly, since main.go's
// aiStep() plays the walk animation from the returned Path before resolving
// Target. ok=false has the identical fail-closed meaning as
// ApplyNativeAI14237PhysicalAttack (native data unavailable for this unit --
// caller falls back to its own normalized planning entirely). ok=true,
// plan=nil means native authoritatively found no worthwhile physical attack
// anywhere reachable (caller still runs its own movement-only planning).
func (s *State) nativeAI14237Plan(u *Unit) (plan *AIPlan, ok bool) {
	if s == nil || u == nil || !u.HasNativeRecordByte6 ||
		len(s.NativeItemEffectRows) == 0 || len(s.NativeTerrainMoveCodes) != s.W*s.H {
		return nil, false
	}
	actorIndex := -1
	for i, unit := range s.Units {
		if unit == u {
			actorIndex = i
			break
		}
	}
	if actorIndex < 0 {
		return nil, false
	}
	costRow, okRow := s.nativeMovementCostRowFor(u)
	if !okRow {
		return nil, false
	}
	baseFlags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, false
	}
	records, err := NativeAIScoringRecords(s.Units)
	if err != nil {
		return nil, false
	}
	selector := int(u.NativeRecordByte6)

	result, err := ScoreNativeAI14237(
		s.W, s.H, records, len(s.Units), actorIndex, selector,
		s.NativeItemEffectRows, baseFlags, s.NativeTerrainMoveCodes, costRow,
	)
	if err != nil {
		return nil, false
	}
	if !result.HasWinner {
		return nil, true
	}
	if result.TargetIndex < 0 || result.TargetIndex >= len(s.Units) {
		return nil, false
	}
	target := s.Units[result.TargetIndex]
	if target == nil {
		return nil, false
	}
	p := &AIPlan{U: u, Target: target, SpellID: -1, ItemID: -1, NativeScoredCommands: s.nativeAIPlanScoredCommands(u), NativeSourced: true}
	if u.X != result.Destination.X || u.Y != result.Destination.Y {
		p.Path = s.Path(u, result.Destination.X, result.Destination.Y)
	}
	return p, true
}

// ApplyNativeAI14237PhysicalAttack tries the disassembly-confirmed native
// physical-attack decision (destination+target, ScoreNativeAI14237 in
// native_ai_14237.go) for u.
//
// ok=false means native data wasn't fully available for this unit/state (no
// raw camp provenance, no bound item-effect-row table, incomplete terrain/
// movement-cost data, or a malformed roster) -- the caller must fall back to
// its own legacy approximation entirely, exactly as every other native
// fallback function in this package already does.
//
// ok=true, attacked=false means the native decision authoritatively
// searched every reachable destination and found no worthwhile physical
// attack anywhere -- the caller should still run its own movement-toward-
// nearest-enemy fallback (this function never moves in that case), just
// skip the normalized attack heuristic that would otherwise second-guess a
// real "there is nothing to attack" answer.
//
// ok=true, attacked=true means this function already moved u to the winning
// destination (if it wasn't already there) and executed the attack via the
// existing s.Attack -- the caller's turn for u is complete.
func (s *State) ApplyNativeAI14237PhysicalAttack(u *Unit) (attacked bool, ok bool) {
	if s == nil || u == nil || !u.HasNativeRecordByte6 ||
		len(s.NativeItemEffectRows) == 0 || len(s.NativeTerrainMoveCodes) != s.W*s.H {
		return false, false
	}
	actorIndex := -1
	for i, unit := range s.Units {
		if unit == u {
			actorIndex = i
			break
		}
	}
	if actorIndex < 0 {
		return false, false
	}
	costRow, okRow := s.nativeMovementCostRowFor(u)
	if !okRow {
		return false, false
	}
	baseFlags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return false, false
	}
	records, err := NativeAIScoringRecords(s.Units)
	if err != nil {
		return false, false
	}
	selector := int(u.NativeRecordByte6)

	result, err := ScoreNativeAI14237(
		s.W, s.H, records, len(s.Units), actorIndex, selector,
		s.NativeItemEffectRows, baseFlags, s.NativeTerrainMoveCodes, costRow,
	)
	if err != nil {
		return false, false
	}
	if !result.HasWinner {
		return false, true
	}
	if result.TargetIndex < 0 || result.TargetIndex >= len(s.Units) {
		return false, false
	}
	target := s.Units[result.TargetIndex]
	if target == nil {
		return false, false
	}
	if u.X != result.Destination.X || u.Y != result.Destination.Y {
		u.SetMapPlacement(result.Destination.X, result.Destination.Y, u.Dir)
	}
	s.Attack(u, target)
	return true, true
}
