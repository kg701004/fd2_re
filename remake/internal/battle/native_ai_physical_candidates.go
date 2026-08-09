package battle

import "fmt"

// NativeAIPhysicalAttackGeometry 保存 0x14237 呼叫 0x14818 時由 caller
// 提供的原始幾何參數。欄位只描述 call-site 角色，不把 mode、inner marker
// 或 target code 命名成武器射程、範圍或陣營。
type NativeAIPhysicalAttackGeometry struct {
	TargetMode      int
	TargetInnerMark int
	TargetCode      int
}

// NativeAIPhysicalAttackRawCandidate 是一個落點／目標索引及其 0x50-byte
// 原始記錄快照。resolver 只能從這些快照與 caller-owned 的位址資料產生
// NativePhysicalAttackScoreInput；不可以用 Unit 的 Camp、X/Y 或 normalized
// 戰鬥數值補齊缺少的 raw provenance。
type NativeAIPhysicalAttackRawCandidate struct {
	Destination  Cell
	TargetIndex  int
	ActorRecord  []byte
	TargetRecord []byte
}

// NativeAIPhysicalAttackScoreResolver 將已閉合的 raw 候選轉成評分器的
// word/byte 輸入。地形修正、0x1DEBE 結果及 target +8 等 caller-owned
// provenance 必須由 resolver 明示提供；缺資料時應回傳錯誤。
type NativeAIPhysicalAttackScoreResolver func(
	NativeAIPhysicalAttackRawCandidate,
) (NativePhysicalAttackScoreInput, error)

// BuildNativeAIPhysicalAttackCandidates 串起 0x14237 已證實的無副作用前綴：
//
//	0x145cd→0x4e040→0x146d1→0x14b16
//	→0x14818 target geometry→raw score-input resolver
//
// movementFlags 與 targetFlags 都是 caller-owned 的 live composition snapshot，
// 不會從 immutable FDFIELD 或 normalized State 推導另一份旗標。落點維持
// NativeAIPhysicalDestinations 的 Y-first/X-second 順序；每個落點的目標維持
// runtime record 順序。這個函式只產生候選，不選勝者、不移動、不攻擊，也不
// 接入 NextAIPlan；任何缺少 raw record、幾何或 score provenance 都失敗即關閉。
func BuildNativeAIPhysicalAttackCandidates(
	w, h int,
	records []byte,
	count, actor, selector, initialBudget int,
	geometry NativeAIPhysicalAttackGeometry,
	movementFlags, targetFlags, terrainMoveCodes, costRow []byte,
	resolve NativeAIPhysicalAttackScoreResolver,
) ([]NativePhysicalAttackCandidate, error) {
	if count <= 0 || len(records) != count*nativeRecordSize {
		return nil, fmt.Errorf("native AI physical candidate roster is malformed")
	}
	if resolve == nil {
		return nil, fmt.Errorf("native AI physical candidate score resolver is unavailable")
	}
	if len(targetFlags) != w*h {
		return nil, fmt.Errorf("native AI physical target grid is malformed")
	}
	if geometry.TargetMode < 0 || geometry.TargetMode > 0xff ||
		geometry.TargetInnerMark < 0 || geometry.TargetInnerMark > 0xff ||
		geometry.TargetCode < 0 || geometry.TargetCode > 3 {
		return nil, fmt.Errorf("native AI physical target geometry is malformed")
	}

	destinations, err := NativeAIPhysicalDestinations(
		w, h, records, count, actor, selector, initialBudget,
		movementFlags, terrainMoveCodes, costRow,
	)
	if err != nil {
		return nil, err
	}

	result := make([]NativePhysicalAttackCandidate, 0)
	for _, destination := range destinations {
		targets, err := nativeAIPhysicalTargetIndices(
			w, h, records, count, destination,
			geometry.TargetMode, geometry.TargetInnerMark, geometry.TargetCode,
			targetFlags,
		)
		if err != nil {
			return nil, err
		}
		for _, targetIndex := range targets {
			index := int(targetIndex)
			candidate, err := resolve(NativeAIPhysicalAttackRawCandidate{
				Destination:  destination,
				TargetIndex:  index,
				ActorRecord:  append([]byte(nil), records[actor*nativeRecordSize:(actor+1)*nativeRecordSize]...),
				TargetRecord: append([]byte(nil), records[index*nativeRecordSize:(index+1)*nativeRecordSize]...),
			})
			if err != nil {
				return nil, fmt.Errorf(
					"native AI physical candidate (%d,%d)/%d: %w",
					destination.X, destination.Y, index, err,
				)
			}
			result = append(result, NativePhysicalAttackCandidate{
				DestinationX: destination.X,
				DestinationY: destination.Y,
				TargetIndex:  index,
				Inputs:       candidate,
			})
		}
	}
	return result, nil
}

// nativeAIPhysicalTargetIndices 保存 0x14818 的 cell geometry 與 raw +5/+6
// roster 過濾。它刻意不讀 Unit 投影；targetFlags 必須是該 caller 在這個
// candidate lifetime 中提供的 composition snapshot。
func nativeAIPhysicalTargetIndices(
	w, h int,
	records []byte,
	count int,
	origin Cell,
	mode, innerMark, targetCode int,
	targetFlags []byte,
) ([]byte, error) {
	if count <= 0 || len(records) != count*nativeRecordSize {
		return nil, fmt.Errorf("native AI physical target roster is malformed")
	}
	if innerMark < 0 || targetCode < 0 || targetCode > 3 {
		return nil, fmt.Errorf("native AI physical target geometry is malformed")
	}
	cells, err := NativeCommandTargetCells(w, h, origin, mode, targetFlags)
	if err != nil {
		return nil, err
	}
	result := make([]byte, 0)
	for index := 0; index < count; index++ {
		record := records[index*nativeRecordSize:]
		if record[5]&1 != 0 || !nativeAIScoredRawTargetMatches(targetCode, record[6]) {
			continue
		}
		cell := Cell{X: int(record[0]), Y: int(record[1])}
		if cell.X < 0 || cell.Y < 0 || cell.X >= w || cell.Y >= h {
			return nil, fmt.Errorf("native AI physical target %d is outside the grid", index)
		}
		if !cells[cell] {
			continue
		}
		if mode < 0x10 && innerMark > 0 &&
			absInt(cell.X-origin.X)+absInt(cell.Y-origin.Y) < innerMark {
			continue
		}
		result = append(result, byte(index))
	}
	return result, nil
}
