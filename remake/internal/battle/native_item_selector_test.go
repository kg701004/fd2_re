package battle

import "testing"

func TestAdvanceNativeItemSelectorMatchesTwoColumnInput(t *testing.T) {
	for _, tc := range []struct {
		name                  string
		selection, count, key int
		want                  int
		result                NativeItemSelectorResult
	}{
		{"up wrap", 0, 7, 72, 6, NativeItemSelectorWait},
		{"down crosses column", 3, 7, 80, 4, NativeItemSelectorWait},
		{"down wrap", 6, 7, 80, 0, NativeItemSelectorWait},
		{"left", 6, 7, 75, 2, NativeItemSelectorWait},
		{"left blocked", 2, 7, 75, 2, NativeItemSelectorWait},
		{"right", 2, 7, 77, 6, NativeItemSelectorWait},
		{"right missing", 3, 7, 77, 3, NativeItemSelectorWait},
		{"cancel", 2, 7, 1, 2, NativeItemSelectorCancel},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got, result, err := AdvanceNativeItemSelector(tc.selection, tc.count, tc.key, true, 5)
			if err != nil || got != tc.want || result != tc.result {
				t.Fatalf("got=%d/%d err=%v", got, result, err)
			}
		})
	}
}

func TestAdvanceNativeItemSelectorBattleUseRejectsTypeZero(t *testing.T) {
	if _, result, err := AdvanceNativeItemSelector(0, 1, 28, true, 0); err != nil || result != NativeItemSelectorWait {
		t.Fatalf("battle type0 result=%d err=%v", result, err)
	}
	if _, result, err := AdvanceNativeItemSelector(0, 1, 57, false, 0); err != nil || result != NativeItemSelectorConfirm {
		t.Fatalf("nonbattle type0 result=%d err=%v", result, err)
	}
}

func TestNativeItemSelectorCellsCompactAndUseOriginalGeometry(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	records := make([]byte, nativeRecordSize)
	for slot := 0; slot < 8; slot++ {
		records[0x0a+slot*2] = 0x80
	}
	records[0x0a], records[0x0b] = 0x40, 0
	records[0x0e], records[0x0f] = 0, 79
	cells, err := NativeItemSelectorCells(records, 0, 2, table)
	if err != nil {
		t.Fatal(err)
	}
	if len(cells) != 2 {
		t.Fatalf("cells=%d", len(cells))
	}
	if cells[0].RawSlot != 0 || cells[0].DisplayIndex != 0 ||
		cells[0].LabelX != 42 || cells[0].LabelY != 103 || !cells[0].Equipped ||
		cells[0].CategoryIcon != 62 {
		t.Fatalf("cell0=%#v", cells[0])
	}
	if cells[1].RawSlot != 2 || cells[1].DisplayIndex != 1 ||
		cells[1].LabelX != 42 || cells[1].LabelY != 125 || !cells[1].Selected {
		t.Fatalf("cell1=%#v", cells[1])
	}
}

func TestNativeItemSelectorFifthCellStartsRightColumn(t *testing.T) {
	table, err := LoadNativeItemEffectRowPrefix("../../assets/data/native_item_effect_rows.json")
	if err != nil {
		t.Fatal(err)
	}
	records := make([]byte, nativeRecordSize)
	for slot := 0; slot < 8; slot++ {
		records[0x0a+slot*2], records[0x0b+slot*2] = 0, byte(slot)
	}
	cells, err := NativeItemSelectorCells(records, 0, -1, table)
	if err != nil {
		t.Fatal(err)
	}
	if cells[4].LabelX != 192 || cells[4].LabelY != 103 {
		t.Fatalf("fifth cell=%#v", cells[4])
	}
}
