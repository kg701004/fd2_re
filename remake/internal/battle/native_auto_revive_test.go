package battle

import "testing"

// TestApplyHPDamageAutoRevivesOwnAllyTwicePerBattle is a deliberate
// remake-only QoL feature test (user request): Own/Ally units auto-revive
// to full HP up to twice when a hit would otherwise bring them to 0; a
// third lethal hit in the same battle actually leaves them at 0 HP.
func TestApplyHPDamageAutoRevivesOwnAllyTwicePerBattle(t *testing.T) {
	u := &Unit{Camp: Own, HP: 10, MaxHP: 10}

	u.ApplyHPDamage(15) // 1st lethal hit -> auto-revive #1
	if u.HP != u.MaxHP || u.AutoReviveUsed != 1 {
		t.Fatalf("after 1st lethal hit: hp=%d autoReviveUsed=%d", u.HP, u.AutoReviveUsed)
	}

	u.ApplyHPDamage(15) // 2nd lethal hit -> auto-revive #2
	if u.HP != u.MaxHP || u.AutoReviveUsed != 2 {
		t.Fatalf("after 2nd lethal hit: hp=%d autoReviveUsed=%d", u.HP, u.AutoReviveUsed)
	}

	u.ApplyHPDamage(15) // 3rd lethal hit -> revives exhausted, unit actually dies
	if u.HP != 0 || u.AutoReviveUsed != 2 {
		t.Fatalf("after 3rd lethal hit: hp=%d autoReviveUsed=%d, want dead", u.HP, u.AutoReviveUsed)
	}
}

func TestApplyHPDamageAutoReviveAppliesToAllyNotEnemy(t *testing.T) {
	ally := &Unit{Camp: Ally, HP: 5, MaxHP: 5}
	ally.ApplyHPDamage(10)
	if ally.HP != ally.MaxHP || ally.AutoReviveUsed != 1 {
		t.Fatalf("Ally should auto-revive: hp=%d autoReviveUsed=%d", ally.HP, ally.AutoReviveUsed)
	}

	enemy := &Unit{Camp: Enemy, HP: 5, MaxHP: 5}
	enemy.ApplyHPDamage(10)
	if enemy.HP != 0 || enemy.AutoReviveUsed != 0 {
		t.Fatalf("Enemy must not auto-revive: hp=%d autoReviveUsed=%d", enemy.HP, enemy.AutoReviveUsed)
	}
}

func TestApplyHPDamageAutoReviveDoesNotMarkNativeDeathFlag(t *testing.T) {
	u := &Unit{Camp: Own, HP: 5, MaxHP: 5, HasNativeRecordByte5: true, NativeRecordByte5: 0}
	u.ApplyHPDamage(10)
	if u.HP != u.MaxHP || u.NativeRecordByte5 != 0 {
		t.Fatalf("auto-revived unit must not be flagged dead: hp=%d byte5=%#x", u.HP, u.NativeRecordByte5)
	}
}

func TestApplyHPDamageAutoReviveDoesNotTriggerOnNonLethalDamage(t *testing.T) {
	u := &Unit{Camp: Own, HP: 10, MaxHP: 10}
	u.ApplyHPDamage(4)
	if u.HP != 6 || u.AutoReviveUsed != 0 {
		t.Fatalf("non-lethal damage must not consume a revive: hp=%d autoReviveUsed=%d", u.HP, u.AutoReviveUsed)
	}
}
