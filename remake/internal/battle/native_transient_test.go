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

func TestTickNativeTransientsCampWrapperFailsClosed(t *testing.T) {
	u := &Unit{NativeRecordByte6: 1, HasNativeRecordByte6: true, NativeRecordByte5: 0, HasNativeRecordByte5: true, NativeTransient: [6]byte{1}}
	if got := (&State{Units: []*Unit{u}}).TickNativeTransients(Own); got != nil || u.NativeTransient[0] != 1 {
		t.Fatal("normalized Camp must not be guessed as the native selector")
	}
}
