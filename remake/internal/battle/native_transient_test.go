package battle

import (
	"math/rand"
	"testing"
)

func TestNativeTransientStorageIsBoundedByOriginalOffsets(t *testing.T) {
	u := &Unit{}
	if u.SetNativeTransientDuration(0x21, 3) || u.SetNativeTransientDuration(0x28, 3) {
		t.Fatal("out-of-range raw offsets must be rejected")
	}
	if !u.SetNativeTransientDuration(0x22, 3) || !u.SetNativeTransientDuration(0x27, 1) {
		t.Fatal("recovered transient range must be writable")
	}
	if got, ok := u.NativeTransientDuration(0x22); !ok || got != 3 {
		t.Fatalf("+0x22 = (%d,%v), want (3,true)", got, ok)
	}
	if _, ok := u.NativeTransientDuration(0x28); ok {
		t.Fatal("out-of-range read must fail closed")
	}
}

func TestTickNativeTransientsUsesRawGates(t *testing.T) {
	active := &Unit{Camp: Enemy, OnField: false, HP: 0, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 7, HasNativeRecordByte6: true, NativeTransient: [6]byte{1, 2, 0, 1, 0, 3}}
	otherSelector := &Unit{NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 8, HasNativeRecordByte6: true, NativeTransient: [6]byte{1, 1}}
	blocked := &Unit{NativeRecordByte5: 1, HasNativeRecordByte5: true, NativeRecordByte6: 7, HasNativeRecordByte6: true, NativeTransient: [6]byte{1, 1}}
	missingRaw := &Unit{Camp: Own, OnField: true, HP: 1, NativeTransient: [6]byte{1, 1}}
	st := &State{Units: []*Unit{active, otherSelector, blocked, missingRaw}}

	expired := st.TickNativeTransientsRaw(7)
	if got, want := active.NativeTransient, [6]byte{0, 1, 0, 0, 0, 2}; got != want {
		t.Fatalf("active sweep = %#v, want %#v", got, want)
	}
	if len(expired) != 2 || expired[0].Unit != active || expired[0].Offset != 0x22 || expired[1].Offset != 0x25 {
		t.Fatalf("expiry = %#v, want +0x22/+0x25 for active unit", expired)
	}
	if otherSelector.NativeTransient != [6]byte{1, 1} || blocked.NativeTransient != [6]byte{1, 1} || missingRaw.NativeTransient != [6]byte{1, 1} {
		t.Fatal("units failing the native raw gate must not be decremented")
	}
}

func TestApplyNativeTransientPoisonDamageUsesIndex3AndDoesNotDecrement(t *testing.T) {
	poisoned := &Unit{HP: 100, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 0, HasNativeRecordByte6: true, NativeTransient: [6]byte{0, 0, 0, 5, 0, 0}}
	notPoisoned := &Unit{HP: 100, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 0, HasNativeRecordByte6: true, NativeTransient: [6]byte{1, 1, 1, 0, 1, 1}}
	otherCamp := &Unit{HP: 100, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 1, HasNativeRecordByte6: true, NativeTransient: [6]byte{0, 0, 0, 5, 0, 0}}
	st := &State{Units: []*Unit{poisoned, notPoisoned, otherCamp}}

	damaged := st.ApplyNativeTransientPoisonDamage(0)
	if len(damaged) != 1 || damaged[0].Unit != poisoned || damaged[0].Damage != 10 {
		t.Fatalf("damaged = %#v, want exactly poisoned unit for 10 damage (MaxHP/10)", damaged)
	}
	if poisoned.HP != 90 {
		t.Fatalf("poisoned.HP = %d, want 90", poisoned.HP)
	}
	if poisoned.NativeTransient[3] != 5 {
		t.Fatalf("poison damage must not decrement +0x25, got %d want 5", poisoned.NativeTransient[3])
	}
	if notPoisoned.HP != 100 || otherCamp.HP != 100 {
		t.Fatal("units without index-3 duration or wrong camp must be untouched")
	}
}

func TestApplyNativeTransientPoisonDamageClampsAtZero(t *testing.T) {
	u := &Unit{HP: 3, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 0, HasNativeRecordByte6: true, NativeTransient: [6]byte{0, 0, 0, 1, 0, 0}}
	st := &State{Units: []*Unit{u}}
	damaged := st.ApplyNativeTransientPoisonDamage(0)
	if len(damaged) != 1 || damaged[0].Damage != 3 || u.HP != 0 {
		t.Fatalf("expected clamp to 0 with damage=3, got HP=%d damaged=%#v", u.HP, damaged)
	}
}

func TestNativeCampPhaseOwnRegenMatchesFdotherFormulaAndGates(t *testing.T) {
	// own camp==2, not poisoned(+0x25), not blocked(+0x26): heals MaxHP/5, clamped.
	healable := &Unit{HP: 30, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 2, HasNativeRecordByte6: true}
	nearFull := &Unit{HP: 95, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 2, HasNativeRecordByte6: true}
	poisoned := &Unit{HP: 30, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 2, HasNativeRecordByte6: true, NativeTransient: [6]byte{0, 0, 0, 1, 0, 0}}
	blocked26 := &Unit{HP: 30, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 2, HasNativeRecordByte6: true, NativeTransient: [6]byte{0, 0, 0, 0, 1, 0}}
	notOwn := &Unit{HP: 30, MaxHP: 100, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 1, HasNativeRecordByte6: true}
	st := &State{Units: []*Unit{healable, nearFull, poisoned, blocked26, notOwn}}

	healed := st.NativeCampPhaseOwnRegen()
	if len(healed) != 2 {
		t.Fatalf("healed = %#v, want exactly {healable, nearFull}", healed)
	}
	if healable.HP != 50 { // 30 + 100/5
		t.Fatalf("healable.HP = %d, want 50", healable.HP)
	}
	if nearFull.HP != 100 { // clamp
		t.Fatalf("nearFull.HP = %d, want 100 (clamped)", nearFull.HP)
	}
	if poisoned.HP != 30 || blocked26.HP != 30 || notOwn.HP != 30 {
		t.Fatal("poisoned/blocked/non-own units must not regen")
	}
}

// TestNativeCommand26PoisonLifecycleThroughTickToCommand20Cure proves the
// full inflict(ID26)->camp-phase damage tick->cure(ID20) lifecycle end to
// end through the real command-execution and round-tick entry points, not
// just each piece in isolation. ID26 writes +0x25 (disassembly-confirmed
// poison offset, see ApplyNativeTransientPoisonDamage doc comment); ID20
// clears the same offset the real 0x22A85/0x22AA8/0x22AF6 route reads.
func TestNativeCommand26PoisonLifecycleThroughTickToCommand20Cure(t *testing.T) {
	// Same-camp actor/target with TargetCode 0 mirrors the already-proven
	// working ID26 harness (native_command26_test.go); book[20]'s TargetCode
	// is set to the same value purely so this single unit pair resolves as a
	// valid candidate for both commands in one lifecycle test -- the real
	// per-ID TargetCode values are already independently pinned by
	// native_command20_test.go/native_command26_test.go and are untouched by
	// this choice.
	//
	// caster.NativeRecordByte6 is deliberately 2 (Own reference frame, a
	// no-op for nativeCommandTargetCodeForSelector), not 0: since 2026-08-17
	// TargetCode 0 resolves relative to the caster's own raw selector
	// (NativeCommandTargetMatches), and a selector of 0 (native Enemy) would
	// flip code 0 to require a non-Enemy target -- which this same-camp
	// target is not. target.NativeRecordByte6 stays 0 independently: it is
	// only read by ApplyNativeTransientPoisonDamage(0)/TickNativeTransientsRaw(0)
	// below, which select by the target's own raw camp byte, unrelated to
	// command target-code matching.
	caster := &Unit{Camp: Enemy, OnField: true, HP: 20, MP: 10, X: 0, Y: 0,
		NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 2, HasNativeRecordByte6: true}
	target := &Unit{Camp: Enemy, ClassID: 2, OnField: true, HP: 100, MaxHP: 100, X: 1, Y: 0,
		NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeRecordByte6: 0, HasNativeRecordByte6: true}
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for i := range book {
		book[i] = NativeCommandRecord{ID: i}
	}
	book[10] = NativeCommandRecord{ID: 10, Damage: 100}
	book[26] = NativeCommandRecord{ID: 26, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	book[20] = NativeCommandRecord{ID: 20, SelectionMode: 1, EffectMode: 0, MPCost: 2, TargetCode: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{caster, target}, NativeCompositionEventBytes: make([]byte, 2), NativeCommandBook: book}

	// Step 1: inflict via the real ID26 command path.
	applied, err := st.ExecuteNativeCommandApplication(caster, target, 26, passingNativeApplicationRNG(t), nil)
	if err != nil || len(applied) != 1 || !applied[0].Applied || applied[0].Offset != 0x25 {
		t.Fatalf("ID26 inflict = %#v, err=%v", applied, err)
	}
	if target.NativeTransient[NativeTransientPoisonIndex] == 0 {
		t.Fatal("target must carry a nonzero poison duration after ID26")
	}
	duration := target.NativeTransient[NativeTransientPoisonIndex]
	hpAfterInflict := target.HP

	// Step 2: the same round-boundary tick wired into completeTurn() -- both
	// selector 0 (target's raw camp) passes matching ApplyNativeTransientPoisonDamage
	// then TickNativeTransientsRaw, exactly as cmd/fd2/main.go's completeTurn does.
	poisonDamage := st.ApplyNativeTransientPoisonDamage(0)
	if len(poisonDamage) != 1 || poisonDamage[0].Unit != target || poisonDamage[0].Damage != target.MaxHP/10 {
		t.Fatalf("camp-phase poison damage = %#v", poisonDamage)
	}
	if target.HP != hpAfterInflict-target.MaxHP/10 {
		t.Fatalf("target.HP = %d, want %d", target.HP, hpAfterInflict-target.MaxHP/10)
	}
	st.TickNativeTransientsRaw(0)
	if target.NativeTransient[NativeTransientPoisonIndex] != duration-1 {
		t.Fatalf("tick must decrement duration by exactly 1, got %d want %d", target.NativeTransient[NativeTransientPoisonIndex], duration-1)
	}

	// Step 3: cure via the real ID20 command path.
	cured, err := st.ExecuteNativeCommandClearRestore(caster, target, 20, rand.New(rand.NewSource(2)), nil)
	if err != nil || len(cured) != 1 || !cured[0].Cleared || cured[0].Offset != 0x25 {
		t.Fatalf("ID20 cure = %#v, err=%v", cured, err)
	}
	if target.NativeTransient[NativeTransientPoisonIndex] != 0 {
		t.Fatal("ID20 must clear the poison duration to zero")
	}
	// After cure the camp-phase damage loop must no longer fire.
	if dmg := st.ApplyNativeTransientPoisonDamage(0); len(dmg) != 0 {
		t.Fatalf("cured target must not take further poison damage, got %#v", dmg)
	}
}

func TestTickNativeTransientsCampWrapperFailsClosed(t *testing.T) {
	u := &Unit{NativeRecordByte6: 1, HasNativeRecordByte6: true, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeTransient: [6]byte{1}}
	if got := (&State{Units: []*Unit{u}}).TickNativeTransients(Own); got != nil || u.NativeTransient[0] != 1 {
		t.Fatal("normalized Camp must not be guessed as the native selector")
	}
}
