package battle

import "testing"

func TestResolveNativeAIPhysicalItemSourceMatches14237LookupChain(t *testing.T) {
	record := make([]byte, nativeRecordSize)
	record[0x0a] = 0x40
	record[0x0b] = 1
	record[0x0a+2] = 0x40
	record[0x0b+2] = 0x90 // high item is excluded by 0x1B83D(unit,0)
	rows := make([]byte, 2*NativeItemEffectRowSize)
	rows[NativeItemEffectRowSize+0x0b] = 0x12
	rows[NativeItemEffectRowSize+0x0c] = 0x34

	source, found, err := ResolveNativeAIPhysicalItemSource(record, rows)
	if err != nil || !found {
		t.Fatalf("source=%+v found=%v err=%v", source, found, err)
	}
	if source.Slot != 0 || source.ItemID != 1 ||
		source.RawGeometryByte0B != 0x12 || source.RawGeometryByte0C != 0x34 ||
		len(source.Row) != NativeItemEffectRowSize {
		t.Fatalf("source=%+v", source)
	}
	source.Row[0x0b] = 0xff
	if rows[NativeItemEffectRowSize+0x0b] == 0xff {
		t.Fatal("item row snapshot aliases caller table")
	}
}

func TestResolveNativeAIPhysicalItemSourceKeepsNativeNotFoundAndBoundsClosed(t *testing.T) {
	record := make([]byte, nativeRecordSize)
	record[0x0a] = 0x40
	record[0x0b] = 0x80
	if source, found, err := ResolveNativeAIPhysicalItemSource(
		record, make([]byte, NativeItemEffectRowSize),
	); err != nil || found || source.Row != nil {
		t.Fatalf("high-item source=%+v found=%v err=%v", source, found, err)
	}

	record[0x0b] = 1
	if _, _, err := ResolveNativeAIPhysicalItemSource(
		record, make([]byte, NativeItemEffectRowSize),
	); err == nil {
		t.Fatal("missing item row unexpectedly accepted")
	}
	if _, _, err := ResolveNativeAIPhysicalItemSource(
		record[:nativeRecordSize-1], make([]byte, NativeItemEffectRowSize),
	); err == nil {
		t.Fatal("short runtime record unexpectedly accepted")
	}
}
