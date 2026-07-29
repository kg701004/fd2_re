package fdother

// NativeUnitModeAction 只保存 0x13a9f 模式 2／11 的原始呼叫順序。
// 名稱刻意使用位址，不把函式猜成狂暴、護衛或其他玩法語意。
type NativeUnitModeAction uint8

const (
	NativeModeCall14EF0 NativeUnitModeAction = iota
	NativeModeCall14237
	NativeModeCall1598A
	NativeModeCall15311
	NativeModeCall1548E
	NativeModeCall14121
	NativeModeCall13FD4
)

// PlanNativeUnitMode2 保存 mode 2 的控制流。0x14237 在 0x145c3 固定
// 回傳 0，所以 0x14ef0 失敗時一定接著呼叫 0x13fd4；不會走 0x13e9c。
func PlanNativeUnitMode2(candidateDispatchSucceeded bool) []NativeUnitModeAction {
	if candidateDispatchSucceeded {
		return []NativeUnitModeAction{NativeModeCall14EF0}
	}
	return []NativeUnitModeAction{
		NativeModeCall14EF0,
		NativeModeCall14237,
		NativeModeCall13FD4,
	}
}

// PlanNativeUnitMode11 保存 mode 11 的兩個獨立 signed score gates。
// 0x53c23 >= 6 只控制 0x15311；其後仍會呼叫 0x14237。
// 0x53c4f >= 6 控制 0x1548e，否則才嘗試 0x14121／0x13fd4。
func PlanNativeUnitMode11(
	commandScore int32,
	physicalPriority int32,
	blockedSearchSucceeded bool,
) []NativeUnitModeAction {
	actions := []NativeUnitModeAction{NativeModeCall1598A}
	if commandScore >= 6 {
		actions = append(actions, NativeModeCall15311)
	}
	actions = append(actions, NativeModeCall14237)
	if physicalPriority >= 6 {
		return append(actions, NativeModeCall1548E)
	}
	actions = append(actions, NativeModeCall14121)
	if !blockedSearchSucceeded {
		actions = append(actions, NativeModeCall13FD4)
	}
	return actions
}
