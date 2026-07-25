package battle

import (
	"fmt"
	"math/rand"
)

// NativeCommand24Damage is the state result of player-dispatched native
// command 24.  It is deliberately separate from NativeCommandDamage: this
// route does not read the command's damage/hit bytes or class resistance.
type NativeCommand24Damage struct {
	Target *Unit
	Amount int
	Damage int
}

func nativeCommandDerivedStrikeMultiplier(commandID int) (int, bool) {
	switch commandID {
	case 24:
		return 15, true
	case 28:
		return 20, true
	case 29:
		return 12, true
	case 31:
		return 18, true
	default:
		return 0, false
	}
}

// ResolveNativeCommandDerivedStrikeDamage mirrors the signed amount path in
// 0x276EC -> 0x1C81F: trunc(actor derived AP * multiplier / 10) minus target
// derived DP, then trunc(amount * 9 / 10) plus trunc(rand()%100 * amount / 1000).
// Go integer division truncates toward zero, matching x86 IDIV here.
func ResolveNativeCommandDerivedStrikeDamage(actorAP, targetDP, multiplier int, rng *rand.Rand) (amount, damage int, err error) {
	if rng == nil {
		return 0, 0, fmt.Errorf("nil rng")
	}
	if multiplier <= 0 {
		return 0, 0, fmt.Errorf("invalid native derived-strike multiplier=%d", multiplier)
	}
	amount = actorAP*multiplier/10 - targetDP
	damage = amount*9/10 + rng.Intn(100)*amount/1000
	return amount, damage, nil
}

// ResolveNativeCommand24Damage preserves the ID24-specific public helper.
func ResolveNativeCommand24Damage(actorAP, targetDP int, rng *rand.Rand) (amount, damage int, err error) {
	return ResolveNativeCommandDerivedStrikeDamage(actorAP, targetDP, 15, rng)
}

// ExecuteNativeCommand24 is the recovered non-UI player state slice for
// 0x1CFF0 command 0x18 -> 0x2A6BD -> 0x276EC.  The generic two-stage target
// list and record24 MP debit are followed by the derived-AP/DP damage route.
// The original temporarily restores HP while showing its multi-step effect;
// this state-only slice applies the final equivalent HP delta once.  It does
// not claim the indexed presentation, SFX, timing, or AI dispatcher alias.
func (s *State) ExecuteNativeCommand24(actor, confirmed *Unit, rng *rand.Rand) ([]NativeCommand24Damage, error) {
	return s.ExecuteNativeCommandDerivedStrike(actor, confirmed, 24, rng)
}

// ExecuteNativeCommandDerivedStrike is the state-only 0x276EC family with
// proven player dispatches 24, 28, 29 and 31. ID30 has its own special
// cursor-selector entry point below; IDs32..35 use 0x27FC9 and stay closed.
func (s *State) ExecuteNativeCommandDerivedStrike(actor, confirmed *Unit, commandID int, rng *rand.Rand) ([]NativeCommand24Damage, error) {
	if s == nil || rng == nil {
		return nil, fmt.Errorf("missing native derived-strike state/rng")
	}
	multiplier, ok := nativeCommandDerivedStrikeMultiplier(commandID)
	if !ok {
		return nil, fmt.Errorf("native derived-strike command unavailable id=%d", commandID)
	}
	if len(s.NativeCommandBook) != 36 || s.NativeCommandBook[commandID].ID != commandID {
		return nil, fmt.Errorf("native derived-strike record unavailable id=%d", commandID)
	}
	record := s.NativeCommandBook[commandID]
	targets, err := NativeCommandEffectTargets(s.W, s.H, actor, confirmed, record.SelectionMode, record.EffectMode, record.TargetCode, s.NativeTargetFlags, s.Units)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command 24 insufficient MP")
	}
	results := make([]NativeCommand24Damage, 0, len(targets))
	for _, target := range targets {
		amount, damage, err := ResolveNativeCommandDerivedStrikeDamage(actor.AP, target.DP, multiplier, rng)
		if err != nil {
			return nil, err
		}
		target.HP -= damage
		if target.HP < 0 {
			target.HP = 0
		}
		results = append(results, NativeCommand24Damage{Target: target, Amount: amount, Damage: damage})
	}
	// 0x18D8C applies the invoking actor's completion bit after 0x1CFF0
	// returns success; 0x276EC is such a successful handler route.
	actor.Acted = true
	return results, nil
}

// ExecuteNativeCommand30 is the bounded player state slice for command 30:
// 0x1CFF0 first validates a normal 0x14818 candidate, then 0x149F8 traces
// from the saved pre-confirm cursor toward the confirmed cursor for
// record+3-0x10 steps, before 0x2A6BD -> 0x276EC applies multiplier 18.
// Its indexed multi-hit presentation and UI cursor lifecycle remain outside
// this method; callers must supply both recovered cursor positions.
func (s *State) ExecuteNativeCommand30(actor *Unit, savedCursor, confirmedCursor Cell, rng *rand.Rand) ([]NativeCommand24Damage, error) {
	if s == nil || actor == nil || rng == nil || len(s.NativeCommandBook) != 36 || s.NativeCommandBook[30].ID != 30 {
		return nil, fmt.Errorf("native command 30 state unavailable")
	}
	record := s.NativeCommandBook[30]
	if record.SelectionMode < 0x10 {
		return nil, fmt.Errorf("native command 30 invalid selector mode=%d", record.SelectionMode)
	}
	// The preceding 0x14818 -> 0x115B6 confirmation is still required. It
	// proves the provided confirmed cursor is a valid target candidate before
	// the special line selector is allowed to mutate MP or HP.
	selection, err := NativeCommandTargets(s.W, s.H, Cell{X: actor.X, Y: actor.Y}, record.SelectionMode, record.TargetCode, s.NativeTargetFlags, s.Units)
	if err != nil {
		return nil, err
	}
	confirmed := false
	for _, candidate := range selection {
		if candidate.X == confirmedCursor.X && candidate.Y == confirmedCursor.Y {
			confirmed = true
			break
		}
	}
	if !confirmed {
		return nil, fmt.Errorf("confirmed cursor is not a native command 30 candidate")
	}
	targets, err := NativeCommand30Targets(s.W, s.H, savedCursor, confirmedCursor, record.SelectionMode-0x10, s.Units)
	if err != nil {
		return nil, err
	}
	if !SpendNativeCommandMP(actor, record.MPCost) {
		return nil, fmt.Errorf("native command 30 insufficient MP")
	}
	results := make([]NativeCommand24Damage, 0, len(targets))
	for _, target := range targets {
		amount, damage, err := ResolveNativeCommandDerivedStrikeDamage(actor.AP, target.DP, 18, rng)
		if err != nil {
			return nil, err
		}
		target.HP -= damage
		if target.HP < 0 {
			target.HP = 0
		}
		results = append(results, NativeCommand24Damage{Target: target, Amount: amount, Damage: damage})
	}
	actor.Acted = true
	return results, nil
}
