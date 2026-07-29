package battle

import "fmt"

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

type NativeFieldEvent61Plan struct {
	EventID       byte
	MissingItem   bool
	TextIndex     int
	FinalText     int
	Presentation  NativeFieldPresentation
	JoinCharacter int

	trigger        *Unit
	itemIndex      int
	stateIndex     int
	spawnGroup     int
	requiredFrames int
}

// PlanNativeFieldEvent61 validates the complete editable/native boundary
// before the UI starts text #3 and the 59-frame presentation. Missing item is
// a valid, non-mutating native outcome; malformed provenance fails closed.
func PlanNativeFieldEvent61(
	st *State,
	trigger *Unit,
	x, y int,
) (NativeFieldEvent61Plan, error) {
	if st == nil || trigger == nil || trigger.X != x || trigger.Y != y {
		return NativeFieldEvent61Plan{}, fmt.Errorf("event61: invalid trigger")
	}
	eventID, ok := NativeFieldEventIDAt(st, x, y, 1)
	if !ok || eventID != 61 {
		return NativeFieldEvent61Plan{}, fmt.Errorf("event61: selector1 binding is absent")
	}
	var rule *NativeFieldEventRule
	for i := range st.NativeFieldEventRules {
		if st.NativeFieldEventRules[i].EventID == 61 &&
			st.NativeFieldEventRules[i].Selector == 1 {
			rule = &st.NativeFieldEventRules[i]
			break
		}
	}
	if rule == nil || rule.OnceState == nil || *rule.OnceState != 12 ||
		rule.RequiredItem == nil || *rule.RequiredItem != 0xD0 ||
		!rule.ConsumeItem || rule.SpawnGroup == nil || *rule.SpawnGroup != 1 ||
		rule.JoinCharacter == nil || *rule.JoinCharacter != 31 ||
		rule.TextIndices == nil || rule.Presentation == nil ||
		*rule.TextIndices != (NativeFieldTextIndices{MissingItem: 2, Success: 3, Final: 4}) ||
		*rule.Presentation != (NativeFieldPresentation{
			Archive: "FDOTHER.DAT", Resource: 45, Frames: 59,
			Helper: "0x2935b", DestinationOffset: 48356, Stride: 320,
			Transparent: -1, DelayHelper: "0x17aa9", DelayTicks: 2,
		}) {
		return NativeFieldEvent61Plan{}, fmt.Errorf("event61: editable rule is incomplete")
	}
	if st.NativeEventState[*rule.OnceState] != 0 {
		return NativeFieldEvent61Plan{}, fmt.Errorf("event61: once state is already set")
	}
	if err := ValidateNativeInventoryProjection(trigger); err != nil {
		return NativeFieldEvent61Plan{}, fmt.Errorf("event61: %w", err)
	}
	itemIndex := -1
	for i, item := range trigger.Inventory {
		if item == *rule.RequiredItem {
			itemIndex = i
			break
		}
	}
	plan := NativeFieldEvent61Plan{
		EventID: 61, MissingItem: itemIndex < 0,
		TextIndex: rule.TextIndices.Success, FinalText: rule.TextIndices.Final,
		Presentation: *rule.Presentation, JoinCharacter: *rule.JoinCharacter,
		trigger: trigger, itemIndex: itemIndex, stateIndex: *rule.OnceState,
		spawnGroup: *rule.SpawnGroup, requiredFrames: rule.Presentation.Frames,
	}
	if itemIndex < 0 {
		plan.TextIndex = rule.TextIndices.MissingItem
		return plan, nil
	}
	var pending int
	for _, unit := range st.Roster {
		if unit != nil && unit.Group == plan.spawnGroup {
			if unit.Fig != plan.JoinCharacter || unit.Camp != Own {
				return NativeFieldEvent61Plan{}, fmt.Errorf("event61: pending group identity mismatch")
			}
			pending++
		}
	}
	if pending != 1 {
		return NativeFieldEvent61Plan{}, fmt.Errorf("event61: pending group cardinality is %d", pending)
	}
	return plan, nil
}

// CommitNativeFieldEvent61 applies only the mutations after the caller has
// presented all native frames. It revalidates the plan so cancellation or an
// intervening inventory change cannot consume an item or partially set state.
// Persistent JOIN is intentionally returned to the campaign owner.
func CommitNativeFieldEvent61(
	st *State,
	plan NativeFieldEvent61Plan,
	presentedFrames int,
) (int, error) {
	if st == nil || plan.MissingItem || plan.trigger == nil ||
		presentedFrames != plan.requiredFrames ||
		plan.stateIndex != 12 || st.NativeEventState[plan.stateIndex] != 0 {
		return 0, fmt.Errorf("event61: plan is not committable")
	}
	if err := ValidateNativeInventoryProjection(plan.trigger); err != nil ||
		plan.itemIndex < 0 || plan.itemIndex >= len(plan.trigger.Inventory) ||
		plan.trigger.Inventory[plan.itemIndex] != 0xD0 {
		return 0, fmt.Errorf("event61: trigger inventory changed")
	}
	var pending int
	for _, unit := range st.Roster {
		if unit != nil && unit.Group == plan.spawnGroup &&
			unit.Fig == plan.JoinCharacter && unit.Camp == Own {
			pending++
		}
	}
	if pending != 1 {
		return 0, fmt.Errorf("event61: pending group changed")
	}
	if err := RemoveNativeCompactInventory(plan.trigger, plan.itemIndex); err != nil {
		return 0, err
	}
	st.NativeEventState[plan.stateIndex] = 1
	if appended := st.AppendGroup(plan.spawnGroup); appended != 1 {
		// Preflight made this unreachable for the current representation. Keep
		// the failure explicit instead of claiming campaign JOIN succeeded.
		return 0, fmt.Errorf("event61: group append changed after preflight")
	}
	return plan.JoinCharacter, nil
}
