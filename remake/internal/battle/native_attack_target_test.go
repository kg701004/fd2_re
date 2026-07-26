package battle

import "testing"

func TestNativeAttackCandidatesAppliesInnerRadiusMarker(t *testing.T) {
	units := []*Unit{
		{Camp: Enemy, X: 0, Y: 0, HP: 10, MaxHP: 10, OnField: true},
		{Camp: Enemy, X: 1, Y: 0, HP: 10, MaxHP: 10, OnField: true},
		{Camp: Enemy, X: 2, Y: 0, HP: 10, MaxHP: 10, OnField: true},
	}
	targets, err := NativeAttackCandidates(5, 1, Cell{X: 0, Y: 0}, 3, 2, 0, make([]byte, 5), units)
	if err != nil || len(targets) != 1 || targets[0] != units[2] {
		t.Fatalf("inner-radius candidates=%v err=%v, want only slot2", targets, err)
	}
}

func TestNativeAttackCandidatesCrossSkipsInnerRadius(t *testing.T) {
	units := []*Unit{
		{Camp: Enemy, X: 0, Y: 0, HP: 10, MaxHP: 10, OnField: true},
		{Camp: Enemy, X: 1, Y: 0, HP: 10, MaxHP: 10, OnField: true},
	}
	targets, err := NativeAttackCandidates(3, 1, Cell{X: 0, Y: 0}, 0x11, 99, 0, make([]byte, 3), units)
	if err != nil || len(targets) != 2 {
		t.Fatalf("cross candidates=%v err=%v, want both cells", targets, err)
	}
}

func TestNativeAttackCandidatesRejectsNegativeInnerRadius(t *testing.T) {
	if _, err := NativeAttackCandidates(1, 1, Cell{}, 1, -1, 0, []byte{0}, nil); err == nil {
		t.Fatal("negative inner radius unexpectedly accepted")
	}
}
