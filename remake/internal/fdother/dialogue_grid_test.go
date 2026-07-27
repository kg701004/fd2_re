package fdother

import "testing"

func TestPlanNativeDialogueFrameGridMatches168B6ItemInvocation(t *testing.T) {
	got, err := PlanNativeDialogueFrameGrid(320, 5, 7, 5, 5)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 49 {
		t.Fatalf("placements=%d, want 49", len(got))
	}
	for index, want := range map[int]NativeDialogueGridPlacement{
		0:  {ResourceIndex: 1, DestinationByte: 2245},
		1:  {ResourceIndex: 2, DestinationByte: 2328},
		2:  {ResourceIndex: 3, DestinationByte: 28805},
		3:  {ResourceIndex: 4, DestinationByte: 28888},
		11: {ResourceIndex: 17, DestinationByte: 23768},
		12: {ResourceIndex: 9, DestinationByte: 2264},
		18: {ResourceIndex: 10, DestinationByte: 8325},
		24: {ResourceIndex: 13, DestinationByte: 3208},
		48: {ResourceIndex: 13, DestinationByte: 23752},
	} {
		if got[index] != want {
			t.Fatalf("placement[%d]=%#v, want %#v", index, got[index], want)
		}
	}
}

func TestPlanNativeDialogueFrameGridRejectsInvalidGeometry(t *testing.T) {
	if got, err := PlanNativeDialogueFrameGrid(320, 5, 7, 1, 5); err == nil || got != nil {
		t.Fatalf("placements=%#v err=%v", got, err)
	}
	if got, err := PlanNativeDialogueFrameGrid(16, 5, 7, 5, 5); err == nil || got != nil {
		t.Fatalf("placements=%#v err=%v", got, err)
	}
}
