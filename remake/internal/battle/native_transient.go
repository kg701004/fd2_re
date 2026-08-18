package battle

// NativeTransientOffset is the first byte of the original six-byte transient
// interval at runtime unit+0x22..+0x27.  Callers use raw offsets deliberately:
// only some effects have a recovered gameplay label, and the data layer must
// not invent one for the rest.
const (
	NativeTransientOffset = 0x22
	NativeTransientCount  = 6
)

// NativeTransientExpiry records one original raw interval byte which reached
// zero during the recovered 0x1A866 camp-phase sweep.  Recalculation of
// derived stats/render feedback is intentionally owned by higher layers;
// battle cannot import campaign's equipment table without creating a cycle.
type NativeTransientExpiry struct {
	Unit   *Unit
	Offset int
}

// NativeTransientDuration returns a raw duration byte by its original unit
// offset.  It rejects anything outside +0x22..+0x27 rather than silently
// mapping a guessed status field.
func (u *Unit) NativeTransientDuration(offset int) (byte, bool) {
	if u == nil || offset < NativeTransientOffset || offset >= NativeTransientOffset+NativeTransientCount {
		return 0, false
	}
	return u.NativeTransient[offset-NativeTransientOffset], true
}

// SetNativeTransientDuration writes one recovered raw duration byte.  It is a
// bounded storage primitive; command-specific gates and side effects remain
// in their separately recovered executors.
func (u *Unit) SetNativeTransientDuration(offset int, duration byte) bool {
	if u == nil || offset < NativeTransientOffset || offset >= NativeTransientOffset+NativeTransientCount {
		return false
	}
	u.NativeTransient[offset-NativeTransientOffset] = duration
	return true
}

// TickNativeTransientsRaw mirrors the recovered raw mutation portion of
// 0x1A866. The native routine gates on record+6 == selector and
// (record+5 & 1) == 0; it does not prove an OnField/Alive/Camp equivalence.
// Every nonzero byte +0x22..+0x27 is decremented independently.
func (s *State) TickNativeTransientsRaw(selector byte) []NativeTransientExpiry {
	if s == nil {
		return nil
	}
	var expired []NativeTransientExpiry
	for _, u := range s.Units {
		if u == nil || !u.HasNativeRecordByte6 || u.NativeRecordByte6 != selector ||
			!u.HasNativeRecordByte5 || u.NativeRecordByte5&1 != 0 {
			continue
		}
		for i, duration := range u.NativeTransient {
			if duration == 0 {
				continue
			}
			u.NativeTransient[i]--
			if u.NativeTransient[i] == 0 {
				expired = append(expired, NativeTransientExpiry{Unit: u, Offset: NativeTransientOffset + i})
			}
		}
	}
	return expired
}

// TickNativeTransients is retained for source compatibility only. Camp is a
// normalized remake enum, not the raw selector passed as 0x1A866's argument;
// mapping one to the other would reintroduce the withdrawn assertion. Callers
// must provide the recovered raw selector through TickNativeTransientsRaw.
func (s *State) TickNativeTransients(_ Camp) []NativeTransientExpiry { return nil }

// NativeTransientPoisonIndex is the array index (within NativeTransient) of
// the byte 0x1A866 reads for its unconditional per-camp-phase HP damage loop
// -- disassembly-confirmed 2026-08-14 (Ghidra decompile of the "新版"
// reference EXE, docs/knowledge-base/11-enemy-ai.md "camp-phase 完整流程"):
// 0x1A866's FIRST loop (distinct from and preceding the decrement/expiry
// loop TickNativeTransientsRaw already models) reads record+0x25 --
// NativeTransientOffset(0x22)+3 -- and, if nonzero, subtracts maxHP/10 from
// currentHP (clamped to 0) WITHOUT decrementing the byte itself; only the
// second loop (already in TickNativeTransientsRaw) decrements it and fires
// expiry on reaching zero. The two loops share the same camp/active gate but
// are otherwise independent passes over every unit.
const NativeTransientPoisonIndex = 3

// NativeTransientPoisonDamage records one unit that took 0x1A866's
// unconditional maxHP/10 damage for having a nonzero
// NativeTransient[NativeTransientPoisonIndex].
type NativeTransientPoisonDamage struct {
	Unit   *Unit
	Damage int
}

// ApplyNativeTransientPoisonDamage mirrors 0x1A866's first loop exactly: for
// every unit with record+6==selector and (record+5&1)==0 and a nonzero
// NativeTransient[NativeTransientPoisonIndex], subtract MaxHP/10 from HP
// (integer division, clamped at 0). It does not decrement the byte -- that
// remains TickNativeTransientsRaw's job, called separately for the same
// selector to mirror the real function's second loop.
func (s *State) ApplyNativeTransientPoisonDamage(selector byte) []NativeTransientPoisonDamage {
	if s == nil {
		return nil
	}
	var damaged []NativeTransientPoisonDamage
	for _, u := range s.Units {
		if u == nil || !u.HasNativeRecordByte6 || u.NativeRecordByte6 != selector ||
			!u.HasNativeRecordByte5 || u.NativeRecordByte5&1 != 0 {
			continue
		}
		if u.NativeTransient[NativeTransientPoisonIndex] == 0 {
			continue
		}
		dmg := u.MaxHP / 10
		next := u.HP - dmg
		if next < 0 {
			next = 0
		}
		if actual := u.HP - next; actual != 0 {
			u.HP = next
			damaged = append(damaged, NativeTransientPoisonDamage{Unit: u, Damage: actual})
		}
	}
	return damaged
}

// NativeCampPhaseOwnRegen mirrors 0x1A30B's own-camp natural HP regen sweep
// -- the same formula already proven at the raw-byte level by
// fdother.NativeBattleEntryStep, reproduced here at the Unit level to avoid a
// battle->fdother import cycle. Disassembly-confirmed 2026-08-14: the gate is
// hardcoded to camp==2 (Own) -- not parameterized by selector like 0x1A866 --
// plus (record+5&0x81)==0, NativeTransient[+0x25]==0 (not poisoned), and
// NativeTransient[+0x26]==0 (a second, still-unnamed blocking status). HP
// advances by MaxHP/5 per call, clamped to MaxHP.
func (s *State) NativeCampPhaseOwnRegen() []*Unit {
	if s == nil {
		return nil
	}
	const ownCamp = 2
	var healed []*Unit
	for _, u := range s.Units {
		if u == nil || !u.HasNativeRecordByte6 || u.NativeRecordByte6 != ownCamp ||
			!u.HasNativeRecordByte5 || u.NativeRecordByte5&0x81 != 0 {
			continue
		}
		if u.NativeTransient[NativeTransientPoisonIndex] != 0 || u.NativeTransient[4] != 0 {
			continue
		}
		if u.HP >= u.MaxHP {
			continue
		}
		next := u.HP + u.MaxHP/5
		if next > u.MaxHP {
			next = u.MaxHP
		}
		if next != u.HP {
			u.HP = next
			healed = append(healed, u)
		}
	}
	return healed
}
