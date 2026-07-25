package battle

import (
	"math/rand"
	"testing"
)

func nativeCommand24Book() []NativeCommandRecord {
	book := make([]NativeCommandRecord, 36)
	for id := range book {
		book[id] = NativeCommandRecord{ID: id}
	}
	// Raw record24 is 00 00 00 05 01 16 00: selection=5, effect=1,
	// MP=22, target-code=0.  Damage/hit are intentionally unused here.
	book[24] = NativeCommandRecord{ID: 24, SelectionMode: 5, EffectMode: 1, MPCost: 22, TargetCode: 0}
	return book
}

func TestExecuteNativeCommand24UsesDerivedStatsAndOneMPDebit(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, AP: 100, MP: 30}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, DP: 20, HP: 200}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: nativeCommand24Book()}

	got, err := st.ExecuteNativeCommand24(actor, target, rand.New(rand.NewSource(2)))
	if err != nil || len(got) != 1 || got[0].Target != target || got[0].Amount != 130 || got[0].Damage < 117 || got[0].Damage > 129 {
		t.Fatalf("ID24 result=%#v err=%v", got, err)
	}
	if target.HP != 200-got[0].Damage || actor.MP != 8 || !actor.Acted {
		t.Fatalf("ID24 state actor=%#v target=%#v result=%#v", actor, target, got[0])
	}
}

func TestExecuteNativeCommand24RejectsInvalidBookBeforeMutation(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, MP: 30}
	target := &Unit{Camp: Enemy, OnField: true, HP: 100}
	book := nativeCommand24Book()
	book[24].ID = 0
	st := &State{W: 1, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: []byte{0}, NativeCommandBook: book}
	if _, err := st.ExecuteNativeCommand24(actor, target, rand.New(rand.NewSource(1))); err == nil || actor.MP != 30 || actor.Acted || target.HP != 100 {
		t.Fatalf("invalid ID24 book mutated state actor=%#v target=%#v err=%v", actor, target, err)
	}
}

func TestExecuteNativeCommandDerivedStrikeUsesRecoveredID28Multiplier(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, AP: 100, MP: 30}
	target := &Unit{Camp: Enemy, OnField: true, X: 1, Y: 0, DP: 20, HP: 300}
	book := nativeCommand24Book()
	book[28] = NativeCommandRecord{ID: 28, SelectionMode: 1, EffectMode: 0, MPCost: 22, TargetCode: 0}
	st := &State{W: 2, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 2), NativeCommandBook: book}

	got, err := st.ExecuteNativeCommandDerivedStrike(actor, target, 28, rand.New(rand.NewSource(2)))
	if err != nil || len(got) != 1 || got[0].Amount != 180 || got[0].Damage < 162 || got[0].Damage > 179 {
		t.Fatalf("ID28 result=%#v err=%v", got, err)
	}
	if actor.MP != 8 || !actor.Acted || target.HP != 300-got[0].Damage {
		t.Fatalf("ID28 state actor=%#v target=%#v result=%#v", actor, target, got[0])
	}
}

func TestExecuteNativeCommandDerivedStrikeRejectsSpecialSelectorID30(t *testing.T) {
	actor := &Unit{MP: 30}
	if _, err := (&State{}).ExecuteNativeCommandDerivedStrike(actor, nil, 30, rand.New(rand.NewSource(1))); err == nil || actor.MP != 30 || actor.Acted {
		t.Fatalf("generic derived-strike executor must reject ID30 special selector: actor=%#v err=%v", actor, err)
	}
}

func TestNativeCommand30TargetsUsesSavedCursorAndXPriority(t *testing.T) {
	xLine := &Unit{Camp: Enemy, OnField: true, HP: 1, X: 1, Y: 0}
	yDiagonal := &Unit{Camp: Enemy, OnField: true, HP: 1, X: 0, Y: 1}
	got, err := NativeCommand30Targets(5, 3, Cell{X: 0, Y: 0}, Cell{X: 2, Y: 2}, 4, []*Unit{xLine, yDiagonal})
	if err != nil || len(got) != 1 || got[0] != xLine {
		t.Fatalf("ID30 X-priority targets=%#v err=%v", got, err)
	}
	plusY := &Unit{Camp: Enemy, OnField: true, HP: 1, X: 1, Y: 2}
	got, err = NativeCommand30Targets(3, 4, Cell{X: 1, Y: 1}, Cell{X: 1, Y: 1}, 1, []*Unit{plusY})
	if err != nil || len(got) != 1 || got[0] != plusY {
		t.Fatalf("ID30 equal-cursor must follow native +Y branch: targets=%#v err=%v", got, err)
	}
}

func TestExecuteNativeCommand30UsesSpecialLineAndOneMPDebit(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, AP: 100, MP: 30}
	between := &Unit{Camp: Enemy, OnField: true, X: 2, Y: 0, DP: 20, HP: 300}
	confirmed := &Unit{Camp: Enemy, OnField: true, X: 4, Y: 0, DP: 20, HP: 300}
	friendly := &Unit{Camp: Own, OnField: true, X: 3, Y: 0, DP: 20, HP: 300}
	book := nativeCommand24Book()
	book[30] = NativeCommandRecord{ID: 30, SelectionMode: 20, EffectMode: 0, MPCost: 24, TargetCode: 0}
	st := &State{W: 5, H: 1, Units: []*Unit{actor, between, confirmed, friendly}, NativeTargetFlags: make([]byte, 5), NativeCommandBook: book}

	got, err := st.ExecuteNativeCommand30(actor, Cell{X: 0, Y: 0}, Cell{X: 4, Y: 0}, rand.New(rand.NewSource(2)))
	if err != nil || len(got) != 2 || got[0].Target != between || got[1].Target != confirmed || got[0].Amount != 160 || got[1].Amount != 160 {
		t.Fatalf("ID30 result=%#v err=%v", got, err)
	}
	if actor.MP != 6 || !actor.Acted || friendly.HP != 300 || between.HP >= 300 || confirmed.HP >= 300 {
		t.Fatalf("ID30 mutation actor=%#v between=%#v confirmed=%#v friendly=%#v", actor, between, confirmed, friendly)
	}
}

func TestExecuteNativeCommand30RejectsNonCandidateBeforeMP(t *testing.T) {
	actor := &Unit{Camp: Own, OnField: true, X: 0, Y: 0, AP: 100, MP: 30}
	target := &Unit{Camp: Enemy, OnField: true, X: 4, Y: 0, DP: 20, HP: 300}
	book := nativeCommand24Book()
	book[30] = NativeCommandRecord{ID: 30, SelectionMode: 20, MPCost: 24, TargetCode: 0}
	st := &State{W: 5, H: 1, Units: []*Unit{actor, target}, NativeTargetFlags: make([]byte, 5), NativeCommandBook: book}
	if _, err := st.ExecuteNativeCommand30(actor, Cell{X: 0, Y: 0}, Cell{X: 1, Y: 0}, rand.New(rand.NewSource(2))); err == nil || actor.MP != 30 || actor.Acted || target.HP != 300 {
		t.Fatalf("invalid ID30 confirmation mutated state actor=%#v target=%#v err=%v", actor, target, err)
	}
}
