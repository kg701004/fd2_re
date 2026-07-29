package battle

import "fmt"

// NativeAIScoredCommandGroupScore is the score returned by 0x15b77 for one
// already-resolved 0x1598a destination/target group.
type NativeAIScoredCommandGroupScore struct {
	Destination   Cell
	TargetIndices []byte
	Score         int
}

// ScoreNativeAIScoredCommandGroups dispatches the complete command-index
// families visible in 0x15b77. IDs 23..25 and 28..35 reach the native zero
// return path. The caller still owns comparison against [0x53c23] and the
// command-word tie state; this function deliberately does not select a winner.
func ScoreNativeAIScoredCommandGroups(
	records []byte,
	commandID, commandValue int,
	groups []NativeAIScoredCommandCandidateGroup,
	skip func(int) bool,
) ([]NativeAIScoredCommandGroupScore, error) {
	if commandID < 0 || commandID >= NativeCommandRecordCount || commandValue < 0 {
		return nil, fmt.Errorf("native AI group score: invalid command id/value")
	}
	result := make([]NativeAIScoredCommandGroupScore, 0, len(groups))
	for _, group := range groups {
		score, err := scoreNativeAIScoredCommandTargets(
			records, group.TargetIndices, commandID, commandValue, skip,
		)
		if err != nil {
			return nil, err
		}
		result = append(result, NativeAIScoredCommandGroupScore{
			Destination:   group.Destination,
			TargetIndices: append([]byte(nil), group.TargetIndices...),
			Score:         score,
		})
	}
	return result, nil
}

func scoreNativeAIScoredCommandTargets(
	records []byte,
	targets []byte,
	commandID, commandValue int,
	skip func(int) bool,
) (int, error) {
	switch {
	case commandID <= 12:
		return ScoreNativeAISpellAttack(records, targets, commandID, commandValue, skip)
	case commandID <= 16:
		return ScoreNativeAISpellRecovery(records, targets, commandID)
	case commandID <= 19:
		return ScoreNativeAISpellZeroFlag(records, targets, commandID)
	case commandID <= 21:
		return ScoreNativeAISpellFlag(records, targets, commandID)
	case commandID == 22:
		return ScoreNativeAISpell22(records, targets)
	case commandID <= 25:
		return 0, nil
	case commandID <= 27:
		return ScoreNativeAISpellZeroFlag(records, targets, commandID)
	default:
		return 0, nil
	}
}
