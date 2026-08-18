package battle

import (
	"fmt"
	"math"
	"math/rand"
)

// NativeCommandModifierApplyResult records one final target in the ID17/18/19
// cast route (魔刃術/魔鎧術/風行術 per docs/data/command_labels.json).
type NativeCommandModifierApplyResult struct {
	Target   *Unit
	Offset   int
	Applied  bool
	Delta    int
	Duration byte
}

// ExecuteNativeCommandModifier casts IDs 17/18/19: the raw mutation formula
// is proven at the byte level by ApplyNativeRawWordStepAtOffsets (0x22721/
// 0x22866, +0x22/+0x23 marker with derived-word delta trunc(current*0.15+1))
// and by ID19's plain flag/+15/+15 pair -- this is that formula's Unit-level
// twin, in the same style as ExecuteNativeCommandClearRestore/
// ExecuteNativeCommandApplication (target resolution + MP via the shared
// helpers, math/rand standing in for the native RNG stream exactly as those
// two already do). Like them, only a target whose relevant transient byte is
// currently zero is affected; a nonzero byte means the buff is already
// active and this command is a no-op for that target (matches the raw gate
// in ApplyNativeRawWordStepAtOffsets/native ID19's own record+0x24 check).
//
// NOT reproduced: expiry-driven removal. The real game's bonus is removed
// only because TickNativeTransientsRaw's zero-crossing calls 0x1B750, which
// recomputes AP/DP/HIT/EV from base+equipment from scratch -- the temporary
// word delta was never a separate tracked quantity, so a full recompute
// simply doesn't reproduce it. This engine has no Unit-level equipment
// recompute bridge yet (ApplyNativeRuntimeEquipmentRecalc operates on raw
// []byte + itemTable, not *Unit), so u.AP/u.DP/u.HIT/u.EV here would drift
// upward forever across repeated casts without ever being subtracted back.
// Do not "fix" this with a naive subtract-on-expiry: the real removal is a
// full recompute, not an inverse delta, and those can differ once equipment
// or other buffs change mid-duration.
func (s *State) ExecuteNativeCommandModifier(actor, confirmed *Unit, commandID int, rng *rand.Rand, scoredDestination *Cell) ([]NativeCommandModifierApplyResult, error) {
	if s == nil || rng == nil {
		return nil, fmt.Errorf("missing native command modifier state/rng")
	}
	offset := 0
	switch commandID {
	case 17, 18, 19:
		offset = NativeTransientOffset + (commandID - 17)
	default:
		return nil, fmt.Errorf("native command modifier unavailable id=%d", commandID)
	}
	if len(s.NativeCommandBook) != NativeCommandRecordCount || s.NativeCommandBook[commandID].ID != commandID {
		return nil, fmt.Errorf("native command modifier record unavailable id=%d", commandID)
	}
	record := s.NativeCommandBook[commandID]
	flags, err := s.NativeCommandBaseFlags()
	if err != nil {
		return nil, err
	}
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, flags, s.Units, scoredDestination)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command modifier insufficient MP")
	}
	results := make([]NativeCommandModifierApplyResult, 0, len(targets))
	for _, target := range targets {
		result := NativeCommandModifierApplyResult{Target: target, Offset: offset}
		if duration, _ := target.NativeTransientDuration(offset); duration == 0 {
			result.Duration = byte(rng.Intn(4) + 2)
			target.SetNativeTransientDuration(offset, result.Duration)
			switch commandID {
			case 17:
				result.Delta = int(math.Trunc(float64(target.AP)*0.15 + 1.0))
				target.AP += result.Delta
			case 18:
				result.Delta = int(math.Trunc(float64(target.DP)*0.15 + 1.0))
				target.DP += result.Delta
			case 19:
				target.HIT += 15
				target.EV += 15
			}
			result.Applied = true
		}
		results = append(results, result)
	}
	actor.Acted = true
	return results, nil
}
