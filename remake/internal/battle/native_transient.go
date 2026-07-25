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

// TickNativeTransients mirrors the raw mutation portion of 0x1A866(camp): on
// a camp phase boundary it visits active, alive units in that camp and
// decrements every nonzero byte +0x22..+0x27 independently.  Expiry is
// reported precisely when a byte becomes zero.  It deliberately does not
// reuse Unit.TickStatus, whose normalized shared timers are not the native ABI.
func (s *State) TickNativeTransients(camp Camp) []NativeTransientExpiry {
	if s == nil {
		return nil
	}
	var expired []NativeTransientExpiry
	for _, u := range s.Units {
		if u == nil || u.Camp != camp || !u.OnField || !u.Alive() {
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
