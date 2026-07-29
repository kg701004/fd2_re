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
