package battle

import "testing"

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

func TestTickNativeTransientsMatchesSeparateCampPhaseSweep(t *testing.T) {
	active := &Unit{Camp: Own, OnField: true, HP: 1, NativeTransient: [6]byte{1, 2, 0, 1, 0, 3}}
	otherCamp := &Unit{Camp: Enemy, OnField: true, HP: 1, NativeTransient: [6]byte{1, 1}}
	inactive := &Unit{Camp: Own, OnField: false, HP: 1, NativeTransient: [6]byte{1, 1}}
	dead := &Unit{Camp: Own, OnField: true, HP: 0, NativeTransient: [6]byte{1, 1}}
	st := &State{Units: []*Unit{active, otherCamp, inactive, dead}}

	expired := st.TickNativeTransients(Own)
	if got, want := active.NativeTransient, [6]byte{0, 1, 0, 0, 0, 2}; got != want {
		t.Fatalf("active sweep = %#v, want %#v", got, want)
	}
	if len(expired) != 2 || expired[0].Unit != active || expired[0].Offset != 0x22 || expired[1].Offset != 0x25 {
		t.Fatalf("expiry = %#v, want +0x22/+0x25 for active unit", expired)
	}
	if otherCamp.NativeTransient != [6]byte{1, 1} || inactive.NativeTransient != [6]byte{1, 1} || dead.NativeTransient != [6]byte{1, 1} {
		t.Fatal("only active units in the requested camp may be decremented")
	}
}
