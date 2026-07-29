package battle

// NativeFieldEventIDAt 保存 0x13a44 的格子事件 selector：
// 該格必須具有已驗證的 0..15 slot，event_id 不得為 0xff，且列內 selector
// 必須等於 caller selector。資料缺失時失敗即關閉。
func NativeFieldEventIDAt(
	st *State,
	x, y int,
	selector byte,
) (byte, bool) {
	if st == nil ||
		st.W <= 0 ||
		st.H <= 0 ||
		len(st.NativeFieldEventSlots) != st.W*st.H ||
		len(st.NativeFieldEvents) != 16 ||
		x < 0 || x >= st.W ||
		y < 0 || y >= st.H {
		return 0, false
	}
	slot := st.NativeFieldEventSlots[y*st.W+x]
	if slot < 0 || slot >= len(st.NativeFieldEvents) {
		return 0, false
	}
	event := st.NativeFieldEvents[slot]
	if event.EventID == 0xff || event.Selector != selector {
		return 0, false
	}
	return event.EventID, true
}

// ApplyNativeFieldModeEvent 執行目前已閉合的 event59/60 mode-range 規則。
// selector 的呼叫時機仍由上層保存；非 mode 規則（包含 event61）不在此猜測執行。
func ApplyNativeFieldModeEvent(
	st *State,
	trigger *Unit,
	x, y int,
	selector byte,
) (byte, bool) {
	eventID, ok := NativeFieldEventIDAt(st, x, y, selector)
	if !ok || trigger == nil {
		return 0, false
	}
	var rule *NativeFieldEventRule
	for i := range st.NativeFieldEventRules {
		if st.NativeFieldEventRules[i].EventID == int(eventID) &&
			st.NativeFieldEventRules[i].Selector == selector {
			rule = &st.NativeFieldEventRules[i]
			break
		}
	}
	if rule == nil || len(rule.SetModeRanges) == 0 {
		return 0, false
	}
	if rule.TriggerGate != "record_byte6_nonzero" ||
		!trigger.HasNativeRecordByte6 ||
		trigger.NativeRecordByte6 == 0 {
		return 0, false
	}
	for _, modeRange := range rule.SetModeRanges {
		if modeRange.Start < 0 || modeRange.End >= len(st.Units) {
			return 0, false
		}
		for index := modeRange.Start; index <= modeRange.End; index++ {
			if st.Units[index] == nil || !st.Units[index].HasNativeRecordByte34 {
				return 0, false
			}
		}
	}
	for _, modeRange := range rule.SetModeRanges {
		for index := modeRange.Start; index <= modeRange.End; index++ {
			u := st.Units[index]
			u.NativeRecordByte34 = (u.NativeRecordByte34 & 0xF0) | modeRange.Mode
		}
	}
	return eventID, true
}
