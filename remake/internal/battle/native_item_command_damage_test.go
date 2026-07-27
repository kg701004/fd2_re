package battle

import (
	"math/rand"
	"testing"
)

func TestNativeType21ReusesCommandDamageWithoutConsumingSource(t *testing.T) {
	route, ok := NativeItemCommandDamageRouteForType(21, 6)
	if !ok || route.CommandID != 6 || route.ConsumesSource {
		t.Fatalf("route = %#v, %v", route, ok)
	}
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id].ID = id
	}
	book[6] = NativeCommandRecord{ID: 6, Damage: 100, Hit: 100}
	targets := []*Unit{{ClassID: 3, HP: 200, MaxHP: 200}, {ClassID: 3, HP: 200, MaxHP: 200}}
	results, err := ApplyNativeItemCommandDamage(targets, route, book, map[int]int{3: 10}, rand.New(rand.NewSource(1)))
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 || !results[0].Hit || !results[1].Hit || targets[0].HP >= 200 || targets[1].HP >= 200 {
		t.Fatalf("results=%#v hp=%d/%d", results, targets[0].HP, targets[1].HP)
	}
}

func TestNativeType21PreflightsAllTargets(t *testing.T) {
	route, _ := NativeItemCommandDamageRouteForType(21, 1)
	book := make([]NativeCommandRecord, NativeCommandRecordCount)
	for id := range book {
		book[id].ID = id
	}
	book[1] = NativeCommandRecord{ID: 1, Damage: 100, Hit: 100}
	first := &Unit{ClassID: 3, HP: 200, MaxHP: 200}
	if _, err := ApplyNativeItemCommandDamage(
		[]*Unit{first, {ClassID: 4, HP: 200, MaxHP: 200}},
		route, book, map[int]int{3: 10}, rand.New(rand.NewSource(1)),
	); err == nil {
		t.Fatal("missing resistance unexpectedly accepted")
	}
	if first.HP != 200 {
		t.Fatalf("first target mutated before preflight: hp=%d", first.HP)
	}
}

func TestNativeType21RejectsNonCommandWord(t *testing.T) {
	if _, ok := NativeItemCommandDamageRouteForType(21, NativeCommandRecordCount); ok {
		t.Fatal("out-of-range command word unexpectedly accepted")
	}
	if _, ok := NativeItemCommandDamageRouteForType(20, 1); ok {
		t.Fatal("wrong item type unexpectedly accepted")
	}
}
