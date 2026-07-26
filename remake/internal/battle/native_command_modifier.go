package battle

import "fmt"

// NativeCommandModifierResult is the raw-only result of command IDs 17..19.
// The union fields preserve the distinct native branch shapes without naming
// the mutated words as gameplay stats.
type NativeCommandModifierResult struct {
	CommandID   int
	WordSteps   []NativeRawWordStepResult
	PairSteps   []NativeRawPairStepResult
	RNGState    uint16
	Accumulator int
}

// ApplyNativeCommandModifier dispatches the proven command table branches:
// ID17→0x22721 (+0x22/+0x48), ID18→0x22866 (+0x23/+0x4a), and
// ID19→0x22997 (+0x24/+0x4c/+0x4e). It deliberately excludes command MP
// debit, target selection, presentation, and any stat/effect naming.
func ApplyNativeCommandModifier(records []byte, unitIndices []byte, commandID int, rngState uint16) (NativeCommandModifierResult, error) {
	if commandID < 17 || commandID > 19 {
		return NativeCommandModifierResult{}, fmt.Errorf("native modifier: unsupported command id %d", commandID)
	}
	result := NativeCommandModifierResult{CommandID: commandID}
	switch commandID {
	case 17:
		steps, state, score, err := ApplyNativeRawWordStepAtOffsets(records, unitIndices, rngState, 0x22, 0x48)
		if err != nil {
			return NativeCommandModifierResult{}, err
		}
		result.WordSteps, result.RNGState, result.Accumulator = steps, state, score
	case 18:
		steps, state, score, err := ApplyNativeRawWordStepAtOffsets(records, unitIndices, rngState, 0x23, 0x4a)
		if err != nil {
			return NativeCommandModifierResult{}, err
		}
		result.WordSteps, result.RNGState, result.Accumulator = steps, state, score
	case 19:
		steps, state, score, err := ApplyNativeRawPairStep(records, unitIndices, rngState)
		if err != nil {
			return NativeCommandModifierResult{}, err
		}
		result.PairSteps, result.RNGState, result.Accumulator = steps, state, score
	}
	return result, nil
}
