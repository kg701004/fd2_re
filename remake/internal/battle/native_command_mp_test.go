package battle

import "testing"

func TestSpendNativeCommandMPMatchesConfirmedNativeDeduction(t *testing.T) {
	u := &Unit{MP: 9, MaxMP: 12}
	if !SpendNativeCommandMP(u, 6) || u.MP != 3 {
		t.Fatalf("successful native deduction: unit=%+v", u)
	}
}

func TestSpendNativeCommandMPFailsClosedBeforeNativeConfirm(t *testing.T) {
	u := &Unit{MP: 5, MaxMP: 5}
	for _, cost := range []int{6, -1, 0x100} {
		if SpendNativeCommandMP(u, cost) || u.MP != 5 {
			t.Fatalf("cost=%d changed unit before valid confirm: %+v", cost, u)
		}
	}
	if SpendNativeCommandMP(nil, 0) {
		t.Fatal("nil unit must fail closed")
	}
}
