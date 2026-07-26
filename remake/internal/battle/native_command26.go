package battle

import (
	"fmt"
	"math/rand"
)

// NativeCommandApplicationResult records one final target in the recovered
// command-26/27 application family. Applied means every native gate passed;
// the raw offset is reported instead of assigning a status name.
type NativeCommandApplicationResult struct {
	Target   *Unit
	Offset   int
	Applied  bool
	Damage   int
	Duration byte
}

// ExecuteNativeCommandApplication executes only the byte-identical common
// route used by IDs 22, 26 and 27: 0x22BE1/0x22CBF/0x22E41 -> 0x22CDA ->
// 0x22D1B.
// It first resolves the generic target contract and spends that command's MP.
// Each final target then needs an empty raw interval, class ID other than 25
// or 26, and rand()%100 < 50; success applies fixed 10 HP damage and writes
// rand()%4+2 to +0x27 (ID22), +0x25 (ID26) or +0x26 (ID27).  It intentionally
// does not map any offset onto the legacy named status approximation.
func (s *State) ExecuteNativeCommandApplication(actor, confirmed *Unit, commandID int, rng *rand.Rand) ([]NativeCommandApplicationResult, error) {
	if s == nil || rng == nil {
		return nil, fmt.Errorf("missing native command application state/rng")
	}
	offset := 0
	switch commandID {
	case 22:
		offset = 0x27
	case 26:
		offset = 0x25
	case 27:
		offset = 0x26
	default:
		return nil, fmt.Errorf("native command application unavailable id=%d", commandID)
	}
	if len(s.NativeCommandBook) != 36 || s.NativeCommandBook[commandID].ID != commandID {
		return nil, fmt.Errorf("native command application record unavailable id=%d", commandID)
	}
	record := s.NativeCommandBook[commandID]
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, s.NativeTargetFlags, s.Units)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command application insufficient MP")
	}
	results := make([]NativeCommandApplicationResult, 0, len(targets))
	for _, target := range targets {
		result := NativeCommandApplicationResult{Target: target, Offset: offset}
		duration, _ := target.NativeTransientDuration(offset)
		if duration == 0 && target.ClassID != 0x19 && target.ClassID != 0x1A && rng.Intn(100) < 50 {
			target.ApplyHPDamage(10) // direct 0x1C81F(target, 10), not record damage math
			result.Applied = true
			result.Damage = 10
			result.Duration = byte(rng.Intn(4) + 2)
			target.SetNativeTransientDuration(offset, result.Duration)
		}
		results = append(results, result)
	}
	actor.Acted = true
	return results, nil
}
