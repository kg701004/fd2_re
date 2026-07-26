package battle

import "testing"

func TestNativeCompoundCommandPlanPreservesRawOrder(t *testing.T) {
	checks := map[int][]NativeCompoundStep{
		32: {{Callee: 0x2111a, CommandID: 32}},
		33: {
			{CommandID: 33, MarkerOffset: 0x25},
			{CommandID: 33, MarkerOffset: 0x26},
			{CommandID: 33, MarkerOffset: 0x27},
			{Callee: 0x211a4, CommandID: 33, Amount: 0x320},
		},
		34: {
			{Callee: 0x22721, CommandID: 17, MarkerOffset: 0x22},
			{Callee: 0x22866, CommandID: 18, MarkerOffset: 0x23},
			{Callee: 0x22997, CommandID: 19, MarkerOffset: 0x24},
		},
		35: {
			{Callee: 0x22d1b, CommandID: 26, MarkerOffset: 0x25},
			{Callee: 0x22d1b, CommandID: 22, MarkerOffset: 0x27},
			{Callee: 0x22d1b, CommandID: 27, MarkerOffset: 0x26},
		},
	}
	for id, want := range checks {
		got, ok := NativeCompoundCommandPlan(id)
		if !ok || len(got) != len(want) {
			t.Fatalf("id %d plan = %#v, %v; want %#v", id, got, ok, want)
		}
		for i := range want {
			if got[i] != want[i] {
				t.Fatalf("id %d step %d = %#v; want %#v", id, i, got[i], want[i])
			}
		}
	}
	if got, ok := NativeCompoundCommandPlan(31); ok || got != nil {
		t.Fatalf("unsupported compound command accepted: %#v, %v", got, ok)
	}
}
