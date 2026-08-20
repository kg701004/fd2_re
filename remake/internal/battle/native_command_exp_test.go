package battle

import (
	"math/rand"
	"testing"
)

func TestNativeCommandExpLevelFactor(t *testing.T) {
	cases := []struct {
		name   string
		target *Unit
		want   int
	}{
		{"nil target", nil, 0},
		{"plain level, non-adjusted class", &Unit{Lv: 5, ClassID: 2}, 5},
		{"class-adjusted lower bound 9", &Unit{Lv: 5, ClassID: 9}, 5 + 0x1e},
		{"class-adjusted upper bound 24", &Unit{Lv: 5, ClassID: 0x18}, 5 + 0x1e},
		{"class 8 excluded (open interval)", &Unit{Lv: 5, ClassID: 8}, 5},
		{"class 0x19 excluded (open interval)", &Unit{Lv: 5, ClassID: 0x19}, 5},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := nativeCommandExpLevelFactor(c.target); got != c.want {
				t.Fatalf("nativeCommandExpLevelFactor(%#v) = %d, want %d", c.target, got, c.want)
			}
		})
	}
}

func TestAwardNativeCommandExpClampsAccumulatorToNinetyNine(t *testing.T) {
	actor := &Unit{Camp: Own, Name: "unregistered-growth-fixture", ClsName: "unregistered-growth-fixture", Lv: 1, MP: 5}
	target := &Unit{Lv: 50} // levelFactor=50; *10 => 500, must clamp to 99 before feeding GainExp
	st := &State{Units: []*Unit{actor, target}}

	st.awardNativeCommandExp(actor, []*Unit{target}, 10, rand.New(rand.NewSource(1)))
	if actor.Exp != 99 {
		t.Fatalf("actor.Exp = %v, want 99 (clamped single-action accumulator)", actor.Exp)
	}
}

func TestAwardNativeCommandExpNoopsForEnemyActorWithoutTouchingRNG(t *testing.T) {
	actor := &Unit{Camp: Enemy, Lv: 1}
	target := &Unit{Lv: 10}
	st := &State{Units: []*Unit{actor, target}}
	source := &countingZeroSource{}

	st.awardNativeCommandExp(actor, []*Unit{target}, 8, rand.New(source))
	if actor.Exp != 0 {
		t.Fatalf("Enemy-camp actor.Exp = %v, want 0 (GainExp no-ops for non Own/Ally)", actor.Exp)
	}
	if source.draws != 0 {
		t.Fatalf("awardNativeCommandExp drew %d RNG values for a zero-gain enemy actor, want 0", source.draws)
	}
}

func TestAwardNativeCommandExpNoopsForEmptyTargetsWithoutTouchingRNG(t *testing.T) {
	actor := &Unit{Camp: Own, Lv: 1}
	st := &State{Units: []*Unit{actor}}
	source := &countingZeroSource{}

	if got := st.awardNativeCommandExp(actor, nil, 8, rand.New(source)); got != nil {
		t.Fatalf("awardNativeCommandExp(nil targets) = %#v, want nil", got)
	}
	if source.draws != 0 {
		t.Fatalf("awardNativeCommandExp drew %d RNG values with no targets, want 0", source.draws)
	}
}
