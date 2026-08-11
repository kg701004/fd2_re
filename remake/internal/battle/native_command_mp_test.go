package battle

import "testing"

// Both tests below use Camp:Enemy deliberately (see native_command0_test.go):
// they lock in the raw native MP-debit math, unaffected by the remake-only
// Own/Ally QoL MP discount (NativeCommandMPCostFor).

func TestSpendNativeCommandMPMatchesConfirmedNativeDeduction(t *testing.T) {
	u := &Unit{Camp: Enemy, MP: 9, MaxMP: 12}
	if !SpendNativeCommandMP(u, 6) || u.MP != 3 {
		t.Fatalf("successful native deduction: unit=%+v", u)
	}
}

func TestSpendNativeCommandMPFailsClosedBeforeNativeConfirm(t *testing.T) {
	u := &Unit{Camp: Enemy, MP: 5, MaxMP: 5}
	for _, cost := range []int{6, -1, 0x100} {
		if SpendNativeCommandMP(u, cost) || u.MP != 5 {
			t.Fatalf("cost=%d changed unit before valid confirm: %+v", cost, u)
		}
	}
	if SpendNativeCommandMP(nil, 0) {
		t.Fatal("nil unit must fail closed")
	}
}

func TestSpendNativeCommandMPAppliesOwnAllyFlatDiscount(t *testing.T) {
	own := &Unit{Camp: Own, MP: 9, MaxMP: 12}
	if !SpendNativeCommandMP(own, 6) || own.MP != 8 {
		t.Fatalf("Own actor should pay flat 1 MP for a >0 cost: unit=%+v", own)
	}
	ally := &Unit{Camp: Ally, MP: 3, MaxMP: 12}
	if !SpendNativeCommandMP(ally, 20) || ally.MP != 2 {
		t.Fatalf("Ally actor should pay flat 1 MP even for an expensive command: unit=%+v", ally)
	}
	free := &Unit{Camp: Own, MP: 0, MaxMP: 12}
	if !SpendNativeCommandMP(free, 0) || free.MP != 0 {
		t.Fatalf("a genuinely free (0 MP) command must stay free: unit=%+v", free)
	}
}
