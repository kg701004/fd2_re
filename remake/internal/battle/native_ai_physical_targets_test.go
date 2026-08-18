package battle

import "testing"

func nativeAIPhysicalTargetsFixtureRecords(units []struct {
	x, y     int
	inactive bool
	camp     byte
}) []byte {
	records := make([]byte, len(units)*nativeRecordSize)
	for i, u := range units {
		r := records[i*nativeRecordSize:]
		r[0], r[1] = byte(u.x), byte(u.y)
		if u.inactive {
			r[5] = 1
		}
		r[6] = u.camp
	}
	return records
}

func TestNativeAIPhysicalAttackTargetsManhattanRangeAndTargetCode(t *testing.T) {
	units := []struct {
		x, y     int
		inactive bool
		camp     byte
	}{
		{5, 5, false, 0}, // enemy, distance 0 from dest (5,5)
		{6, 5, false, 0}, // enemy, distance 1
		{5, 7, false, 0}, // enemy, distance 2 -- out of range 2
		{6, 6, false, 1}, // non-enemy camp, distance 2 -- in range but wrong camp
		{6, 5, true, 0},  // inactive, would match otherwise
	}
	records := nativeAIPhysicalTargetsFixtureRecords(units)

	got, err := NativeAIPhysicalAttackTargets(20, 20, records, len(units), 5, 5, 2, 0)
	if err != nil {
		t.Fatal(err)
	}
	want := []byte{0, 1}
	if len(got) != len(want) {
		t.Fatalf("got %v, want %v", got, want)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("got %v, want %v", got, want)
		}
	}
}

func TestNativeAIPhysicalAttackTargetsFailsClosedOnMalformedInputs(t *testing.T) {
	records := nativeAIPhysicalTargetsFixtureRecords(nil)
	if _, err := NativeAIPhysicalAttackTargets(0, 20, records, 0, 5, 5, 2, 0); err == nil {
		t.Fatal("zero width must fail closed")
	}
	if _, err := NativeAIPhysicalAttackTargets(20, 20, records, 0, -1, 5, 2, 0); err == nil {
		t.Fatal("negative destination must fail closed")
	}
	if _, err := NativeAIPhysicalAttackTargets(20, 20, records, 0, 5, 5, -1, 0); err == nil {
		t.Fatal("negative range must fail closed")
	}
}
