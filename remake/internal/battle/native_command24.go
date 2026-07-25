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

// ResolveNativeCommand24Damage mirrors the signed amount path in
// 0x276EC -> 0x1C81F: trunc(actor derived AP * 15 / 10) minus target derived
// DP, then trunc(amount * 9 / 10) plus trunc(rand()%100 * amount / 1000).
// Go integer division truncates toward zero, matching x86 IDIV here.
func ResolveNativeCommand24Damage(actorAP, targetDP int, rng *rand.Rand) (amount, damage int, err error) {
	if rng == nil {
		return 0, 0, fmt.Errorf("nil rng")
	}
	amount = actorAP*15/10 - targetDP
	damage = amount*9/10 + rng.Intn(100)*amount/1000
	return amount, damage, nil
}

// ExecuteNativeCommand24 is the recovered non-UI player state slice for
// 0x1CFF0 command 0x18 -> 0x2A6BD -> 0x276EC.  The generic two-stage target
// list and record24 MP debit are followed by the derived-AP/DP damage route.
// The original temporarily restores HP while showing its multi-step effect;
// this state-only slice applies the final equivalent HP delta once.  It does
// not claim the indexed presentation, SFX, timing, or AI dispatcher alias.
func (s *State) ExecuteNativeCommand24(actor, confirmed *Unit, rng *rand.Rand) ([]NativeCommand24Damage, error) {
	if s == nil || rng == nil {
		return nil, fmt.Errorf("missing native command 24 state/rng")
	}
	const commandID = 24
	if len(s.NativeCommandBook) != 36 || s.NativeCommandBook[commandID].ID != commandID {
		return nil, fmt.Errorf("native command 24 record unavailable")
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
		amount, damage, err := ResolveNativeCommand24Damage(actor.AP, target.DP, rng)
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
