package battle

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestResolveNativeCommandDamageMatchesRecoveredFormula(t *testing.T) {
	first := fdother.NativeRNGStep(7)
	second := fdother.NativeRNGStep(first)
	base := 50 * 7 / 10
	want := base*9/10 + int(second%100)*base/1000
	got, state, err := ResolveNativeCommandDamage(50, 100, 7, 7)
	if err != nil || !got.Hit || got.Damage != want || state != second {
		t.Fatalf("got %+v state=%#x err=%v, want hit damage=%d state=%#x", got, state, err, want, second)
	}
}

func TestNativeCommandDamageMissDoesNotConsumeVarianceOrMutate(t *testing.T) {
	target := &Unit{HP: 40, MaxHP: 40}
	got, state, err := ApplyNativeCommandDamage(target, 50, 0, 10, 1)
	if err != nil || got.Hit || got.Damage != 0 || target.HP != 40 ||
		state != fdother.NativeRNGStep(1) {
		t.Fatalf("got=%+v state=%#x hp=%d err=%v", got, state, target.HP, err)
	}
}

func TestApplyNativeCommandDamageClampsHP(t *testing.T) {
	// Camp:Enemy is deliberate: locks in the raw HP-clamp-at-zero math,
	// unaffected by the remake-only Own/Ally auto-revive QoL feature.
	target := &Unit{Camp: Enemy, HP: 1, MaxHP: 100}
	got, _, err := ApplyNativeCommandDamage(target, 100, 100, 10, 2)
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
