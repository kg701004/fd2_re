package battle

import "testing"

func TestSetNativeRecordByte5OneOverwritesWholeByte(t *testing.T) {
	records := make([]byte, 2*nativeRecordSize)
	records[5] = 0x80
	records[nativeRecordSize+5] = 0xff
	if err := SetNativeRecordByte5One(records, 1); err != nil {
		t.Fatal(err)
	}
	if records[5] != 0x80 || records[nativeRecordSize+5] != 1 {
		t.Fatalf("bytes=%#x/%#x, want %#x/1", records[5], records[nativeRecordSize+5], 0x80)
	}
}

func TestSetNativeRecordByte5OneRejectsBounds(t *testing.T) {
	if err := SetNativeRecordByte5One(make([]byte, nativeRecordSize), 1); err == nil {
		t.Fatal("out-of-range record unexpectedly accepted")
	}
	if err := SetNativeRecordByte5One(make([]byte, nativeRecordSize), -1); err == nil {
		t.Fatal("negative record unexpectedly accepted")
	}
}

func TestHPWritersMirrorRawByte5OnlyWhenProvenanceExists(t *testing.T) {
	dead := &Unit{HP: 5, MaxHP: 5, HasNativeRecordByte5: true, NativeRecordByte5: 0x80}
	dead.ApplyHPDamage(9)
	if dead.HP != 0 || dead.NativeRecordByte5 != 1 {
		t.Fatalf("native death writer hp=%d byte5=%#x", dead.HP, dead.NativeRecordByte5)
	}
	dead.RestoreNativeHP()
	if dead.HP != 5 || dead.NativeRecordByte5 != 0 {
		t.Fatalf("native revive writer hp=%d byte5=%#x", dead.HP, dead.NativeRecordByte5)
	}

	legacy := &Unit{HP: 5, MaxHP: 5, NativeRecordByte5: 0x80}
	legacy.ApplyHPDamage(9)
	if legacy.HP != 0 || legacy.NativeRecordByte5 != 0x80 {
		t.Fatalf("legacy path fabricated raw provenance hp=%d byte5=%#x", legacy.HP, legacy.NativeRecordByte5)
	}
}
