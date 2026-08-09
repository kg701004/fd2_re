package fdother

// NativeUnitModeAction 只保存 0x13a9f 已閉合模式的原始呼叫／寫入順序。
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
	NativeModeCall13E9C
	NativeModeCall12C60
	NativeModeCall12D7B
	NativeModeCall14B78
	NativeModeCall15DF3
	NativeModeCall1BB8C
	NativeModeCall25B45
	NativeModeCall12263
	NativeModeCall32975
	NativeModeWrite51A83Zero
	NativeModeWriteUnit31And32
	NativeModeWrite53AD5One
	NativeModeWriteUnit34Mode7
)

func nativeMode0FallbackActions(
	blockedSearchSucceeded bool,
	nearestCoordinateSearchSucceeded bool,
) []NativeUnitModeAction {
	actions := []NativeUnitModeAction{NativeModeCall14121}
	if blockedSearchSucceeded {
		return actions
	}
	actions = append(actions, NativeModeCall13E9C)
	if !nearestCoordinateSearchSucceeded {
		actions = append(actions, NativeModeCall13FD4)
	}
	return actions
}

// PlanNativeUnitMode0 保存 mode 0 的原始備援順序。三個布林值都必須由
// 呼叫端以相同 raw 記錄與 callee 回傳值提供；本函式不替它們命名成
// 「攻擊」或「追擊」。0x14121 失敗後才呼叫 0x13e9c，後者回傳 0
// 才會經共用 0x13c06 呼叫 0x13fd4。
func PlanNativeUnitMode0(
	candidateDispatchSucceeded bool,
	blockedSearchSucceeded bool,
	nearestCoordinateSearchSucceeded bool,
) []NativeUnitModeAction {
	if candidateDispatchSucceeded {
		return []NativeUnitModeAction{NativeModeCall14EF0}
	}
	actions := []NativeUnitModeAction{NativeModeCall14EF0}
	return append(actions, nativeMode0FallbackActions(
		blockedSearchSucceeded,
		nearestCoordinateSearchSucceeded,
	)...)
}

// PlanNativeUnitMode1 保存 mode 1 的原始順序。它在 0x14ef0 失敗後只
// 呼叫 0x14121，並透過同一個 0x13c06 分支在回傳 0 時進入 0x13fd4；
// 不會呼叫 mode 0 專用的 0x13e9c。
func PlanNativeUnitMode1(
	candidateDispatchSucceeded bool,
	blockedSearchSucceeded bool,
) []NativeUnitModeAction {
	if candidateDispatchSucceeded {
		return []NativeUnitModeAction{NativeModeCall14EF0}
	}
	actions := []NativeUnitModeAction{NativeModeCall14EF0, NativeModeCall14121}
	if !blockedSearchSucceeded {
		actions = append(actions, NativeModeCall13FD4)
	}
	return actions
}

// PlanNativeUnitMode3 保存 mode 3 的 raw lookup／移動鏈。targetIndex 使用
// 0x12c60 的原始回傳值，負值代表跳到 mode 0 的 0x14121 備援；找到索引
// 後才會呼叫 0x12d7b→0x14b78，零回傳才列入 0x13fd4，最後寫入
// 0x51a83=0。這些輸入都不承載單位或劇情語意。
func PlanNativeUnitMode3(
	candidateDispatchSucceeded bool,
	targetIndex int,
	blockedSearchSucceeded bool,
	nearestCoordinateSearchSucceeded bool,
	movementSucceeded bool,
) []NativeUnitModeAction {
	if candidateDispatchSucceeded {
		return []NativeUnitModeAction{NativeModeCall14EF0}
	}
	actions := []NativeUnitModeAction{NativeModeCall14EF0, NativeModeCall12C60}
	if targetIndex < 0 {
		return append(actions, nativeMode0FallbackActions(
			blockedSearchSucceeded,
			nearestCoordinateSearchSucceeded,
		)...)
	}
	actions = append(actions, NativeModeCall12D7B, NativeModeCall14B78)
	if !movementSucceeded {
		actions = append(actions, NativeModeCall13FD4)
	}
	return append(actions, NativeModeWrite51A83Zero)
}

// PlanNativeUnitMode4 保存全域 0x51a83 清零後的 0x12d7b→0x14b78 鏈。
// 0x14b78 回傳 0 才會進入共用 0x13fd4。
func PlanNativeUnitMode4(movementSucceeded bool) []NativeUnitModeAction {
	actions := []NativeUnitModeAction{
		NativeModeWrite51A83Zero,
		NativeModeCall12D7B,
		NativeModeCall14B78,
	}
	if !movementSucceeded {
		actions = append(actions, NativeModeCall13FD4)
	}
	return actions
}

// NativeUnitMode5Inputs 保存 mode 5 的 raw caller inputs。EventStateByte
// 對應 [0x53ad5+ebp]；EventRecordType 對應 0x53a55 entry 的 byte +0x53。
// 其餘旗標只描述原始 callee 回傳或座標比較，不替欄位命名成玩法。
type NativeUnitMode5Inputs struct {
	CandidateDispatchSucceeded       bool
	EventStateByte                   byte
	EventLookupSucceeded             bool
	MovementSucceeded                bool
	ArrivedAtEventCoordinate         bool
	EventRecordType                  byte
	BlockedSearchSucceeded           bool
	NearestCoordinateSearchSucceeded bool
}

// PlanNativeUnitMode5 保存 mode 5 的事件資料分支與抵達後 raw writes。
// 缺事件狀態或 lookup 失敗時沿用 mode 0 的 0x14121 備援；抵達座標後，
// 只有 EventRecordType<2 才寫入 +0x31/+0x32，且 type==0 才呼叫 0x1bb8c。
func PlanNativeUnitMode5(input NativeUnitMode5Inputs) []NativeUnitModeAction {
	if input.CandidateDispatchSucceeded {
		return []NativeUnitModeAction{NativeModeCall14EF0}
	}
	actions := []NativeUnitModeAction{
		NativeModeCall14EF0,
		NativeModeWrite51A83Zero,
		NativeModeCall12D7B,
	}
	if input.EventStateByte != 0 || !input.EventLookupSucceeded {
		return append(actions, nativeMode0FallbackActions(
			input.BlockedSearchSucceeded,
			input.NearestCoordinateSearchSucceeded,
		)...)
	}
	actions = append(actions, NativeModeCall15DF3, NativeModeCall14B78)
	if !input.MovementSucceeded {
		actions = append(actions, NativeModeCall13FD4)
	}
	if !input.ArrivedAtEventCoordinate {
		return actions
	}
	if input.EventRecordType < 2 {
		actions = append(actions, NativeModeWriteUnit31And32)
		if input.EventRecordType == 0 {
			actions = append(actions, NativeModeCall1BB8C)
		}
	}
	actions = append(actions,
		NativeModeWrite53AD5One,
		NativeModeCall25B45,
		NativeModeCall12263,
		NativeModeWriteUnit34Mode7,
	)
	return actions
}

// PlanNativeUnitMode7 保存 0x51a83 清零、移動與抵達後 0x32975 的順序。
// 座標比對由 caller 以原始 record 提供；即使移動回傳 0 仍保留後續
// 比對閘門，不自行宣稱抵達。
func PlanNativeUnitMode7(movementSucceeded, arrivedAtDestination bool) []NativeUnitModeAction {
	actions := []NativeUnitModeAction{
		NativeModeWrite51A83Zero,
		NativeModeCall12D7B,
		NativeModeCall14B78,
	}
	if !movementSucceeded {
		actions = append(actions, NativeModeCall13FD4)
	}
	if arrivedAtDestination {
		actions = append(actions, NativeModeCall32975)
	}
	return actions
}

// PlanNativeUnitMode9 保存 0x12c60 lookup 後的兩條 raw 路徑。lookup 失敗
// 時回到一般 0x14ef0 起點；找到索引後直接沿用 0x12d7b→0x14b78，零回傳
// 才列入 0x13fd4。
func PlanNativeUnitMode9(
	targetIndex int,
	generalCandidateDispatchSucceeded bool,
	blockedSearchSucceeded bool,
	nearestCoordinateSearchSucceeded bool,
	movementSucceeded bool,
) []NativeUnitModeAction {
	actions := []NativeUnitModeAction{NativeModeCall12C60}
	if targetIndex < 0 {
		return append(actions, PlanNativeUnitMode0(
			generalCandidateDispatchSucceeded,
			blockedSearchSucceeded,
			nearestCoordinateSearchSucceeded,
		)...)
	}
	actions = append(actions, NativeModeCall12D7B, NativeModeCall14B78)
	if !movementSucceeded {
		actions = append(actions, NativeModeCall13FD4)
	}
	return actions
}

// PlanNativeUnitMode10 只在 0x14ef0 失敗時重用 mode 4 的 raw 路徑。
func PlanNativeUnitMode10(candidateDispatchSucceeded, movementSucceeded bool) []NativeUnitModeAction {
	if candidateDispatchSucceeded {
		return []NativeUnitModeAction{NativeModeCall14EF0}
	}
	actions := []NativeUnitModeAction{NativeModeCall14EF0}
	return append(actions, PlanNativeUnitMode4(movementSucceeded)...)
}

// PlanNativeUnitMode2 保存 mode 2 的控制流。0x14ef0 失敗後直接呼叫
// 0x14237，再經 0x13b1e→0x13c06 共用分支；0x14237 的函式尾端以
// xor eax,eax 回傳 0，因此這條失敗路徑會進入 0x13fd4。它不會走
// 0x13e9c。這裡的布林值只表示呼叫端已提供的 0x14ef0 回傳狀態，
// 不把任何位址命名成玩法語意。
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
