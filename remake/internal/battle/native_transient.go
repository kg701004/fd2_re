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
