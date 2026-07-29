package battle

import (
	"testing"

	"github.com/wicanr2/fd2_re/remake/internal/fdother"
)

func TestNativeAIModeRecordForUnitPreservesConstructorBytes(t *testing.T) {
	unit := &Unit{
		NativeRecordByte5: 0x80, HasNativeRecordByte5: true,
		NativeRecordByte34: 0xc2, HasNativeRecordByte34: true,
		NativeRecordByte35: 0x12, HasNativeRecordByte35: true,
		NativeRecordByte36: 0x07, HasNativeRecordByte36: true,
		NativeRecordRace: 4, HasNativeRecordRace: true,
	}
	record, err := NativeAIModeRecordForUnit(unit)
	if err != nil {
		t.Fatal(err)
	}
	if len(record) != 0x3e || record[5] != 0x80 ||
		record[0x34] != 0xc2 || record[0x35] != 0x12 ||
		record[0x36] != 7 || record[0x3d] != 4 {
		t.Fatalf("native AI mode record=%#v", record)
	}
	record[5] = 0
	plan, err := fdother.PlanNativeUnitMode(record, 3, 1)
	if err != nil || plan == nil || plan.Mode != 2 ||
		plan.RawArg35 != 0x12 || plan.RawArg36 != 7 || plan.RawCounter != 4 {
		t.Fatalf("native AI mode plan=%#v err=%v", plan, err)
	}
}

func TestNativeAIModeRecordForUnitFailsClosed(t *testing.T) {
	if _, err := NativeAIModeRecordForUnit(&Unit{}); err == nil {
		t.Fatal("missing mode provenance accepted")
	}
}
