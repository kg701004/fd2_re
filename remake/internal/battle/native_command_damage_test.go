package battle

import (
	"math/rand"
	"os"
	"path/filepath"
	"testing"
)

func TestResolveNativeCommandDamageMatchesRecoveredFormula(t *testing.T) {
	rng := rand.New(rand.NewSource(7))
	// Mirror the two draws explicitly so this checks integer order, not merely a
	// possible range.  50 * 7 / 10 = 35 before the 90..99.9% variance.
	wantRNG := rand.New(rand.NewSource(7))
	if got := wantRNG.Intn(100); got >= 100 {
		t.Fatal("impossible deterministic hit roll")
	}
	base := 50 * 7 / 10
	want := base*9/10 + wantRNG.Intn(100)*base/1000
	got, err := ResolveNativeCommandDamage(50, 100, 7, rng)
	if err != nil || !got.Hit || got.Damage != want {
		t.Fatalf("got %+v err=%v, want hit damage=%d", got, err, want)
	}
}

func TestNativeCommandDamageMissDoesNotConsumeVarianceOrMutate(t *testing.T) {
	rng := rand.New(rand.NewSource(1))
	target := &Unit{HP: 40, MaxHP: 40}
	got, err := ApplyNativeCommandDamage(target, 50, 0, 10, rng)
	if err != nil || got.Hit || got.Damage != 0 || target.HP != 40 {
		t.Fatalf("got=%+v hp=%d err=%v", got, target.HP, err)
	}
	// 0x1c75e returns before the variance draw on a miss.
	wantRNG := rand.New(rand.NewSource(1))
	wantRNG.Intn(100) // hit-roll consumed by the miss
	want := wantRNG.Intn(100)
	if next := rng.Intn(100); next != want {
		t.Fatalf("miss consumed unexpected variance draw: next=%d want=%d", next, want)
	}
}

func TestApplyNativeCommandDamageClampsHP(t *testing.T) {
	target := &Unit{HP: 1, MaxHP: 100}
	got, err := ApplyNativeCommandDamage(target, 100, 100, 10, rand.New(rand.NewSource(2)))
	if err != nil || !got.Hit || got.Damage < 90 || got.Damage > 99 || target.HP != 0 {
		t.Fatalf("got=%+v hp=%d err=%v", got, target.HP, err)
	}
}

func TestLoadNativeCommandResistancesRejectsInvalidEditableData(t *testing.T) {
	path := filepath.Join(t.TempDir(), "resist.json")
	if err := os.WriteFile(path, []byte(`[{"cls":5,"resist_raw":7}]`), 0o600); err != nil {
		t.Fatal(err)
	}
	table, err := LoadNativeCommandResistances(path)
	if err != nil || table[5] != 7 {
		t.Fatalf("table=%v err=%v", table, err)
	}
	if err := os.WriteFile(path, []byte(`[{"cls":5,"resist_raw":11}]`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadNativeCommandResistances(path); err == nil {
		t.Fatal("invalid raw multiplier must fail closed")
	}
}

func TestLoadNativeCommandResistancesRuntimeExport(t *testing.T) {
	table, err := LoadNativeCommandResistances("../../assets/data/native_command_resistances.json")
	if err != nil {
		t.Fatal(err)
	}
	if len(table) != 26 || table[5] != 7 || table[26] != 4 {
		t.Fatalf("unexpected recovered table: classes=%d mage=%d unknown=%d", len(table), table[5], table[26])
	}
}
