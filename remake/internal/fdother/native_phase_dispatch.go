package fdother

import "fmt"

// NativePhaseDispatchCandidate is the raw eligible record observed in the
// 0x1d80b phase loop.  Field names intentionally remain offsets: 0x13a9f
// assigns the event selector and invokes side effects, which are not closed
// by this data-only adapter.
type NativePhaseDispatchCandidate struct {
	UnitIndex   int
	SelectorArg byte
}

// NativePhasePreselectionScores are the two signed globals tested by
// 0x1d92d..0x1d93f after the proven spell-candidate producer 0x1598a and
// item/command-candidate producer 0x1567e.  The address suffixes prevent these
// producer names from being mistaken for individual spell or item semantics.
type NativePhasePreselectionScores struct {
	SpellCandidateScore53C23 int32
	ItemCommandScore53C33    int32
}

// NativePhaseZeroPreselection preserves one eligible +6==0 record in the
// first 0x1d8ba pass.  Both score producers always run; RunUnitAction is true
// only when either signed score is at least six.
type NativePhaseZeroPreselection struct {
	UnitIndex     int
	SelectorArg   byte
	RunUnitAction bool
}

// NativePhaseUnitScanPlan keeps the three loops separate because the original
// invokes the global-event and chapter-handler tables after every unit and may
// stop on a nonzero pending code.  Flattening these slices would lose that
// caller-owned early-exit boundary.
type NativePhaseUnitScanPlan struct {
	SelectorOne      []NativePhaseDispatchCandidate
	ZeroPreselection []NativePhaseZeroPreselection
	ZeroSecondPass   []NativePhaseDispatchCandidate
}

func nativePhaseRecordEligible(record []byte, selector byte) bool {
	return record[6] == selector && record[5]&0x81 == 0 && record[0x26] == 0
}

// FindNativePhaseDispatchCandidates reproduces the first 0x1d80b loop's
// eligibility gate.  Records are 0x50 bytes apart; count is the native global
// [0x53beb].  It does not invoke 0x13a9f or either function table.
func FindNativePhaseDispatchCandidates(records []byte, count int) ([]NativePhaseDispatchCandidate, error) {
	return findNativePhaseDispatchCandidates(records, count, 1)
}

func findNativePhaseDispatchCandidates(
	records []byte,
	count int,
	selector byte,
) ([]NativePhaseDispatchCandidate, error) {
	const stride = 0x50
	if count < 0 {
		return nil, fmt.Errorf("fdother: negative native phase count %d", count)
	}
	if count > 0 && len(records) < count*stride {
		return nil, fmt.Errorf("fdother: native phase records have %d bytes, need %d", len(records), count*stride)
	}
	candidates := make([]NativePhaseDispatchCandidate, 0)
	for unit := 0; unit < count; unit++ {
		record := records[unit*stride : (unit+1)*stride]
		if !nativePhaseRecordEligible(record, selector) {
			continue
		}
		candidates = append(candidates, NativePhaseDispatchCandidate{
			UnitIndex: unit, SelectorArg: selector,
		})
	}
	return candidates, nil
}

// PlanNativePhaseUnitScans reproduces the admission and score gate of
// 0x1d80b, 0x1d8ba and 0x1d988 without invoking 0x13a9f or either callback
// table.  scores must be indexed by native unit index; they are consumed only
// for eligible selector-zero records.
func PlanNativePhaseUnitScans(
	records []byte,
	count int,
	scores []NativePhasePreselectionScores,
) (NativePhaseUnitScanPlan, error) {
	var plan NativePhaseUnitScanPlan
	if count < 0 {
		return plan, fmt.Errorf("fdother: negative native phase count %d", count)
	}
	selectorOne, err := findNativePhaseDispatchCandidates(records, count, 1)
	if err != nil {
		return plan, err
	}
	selectorZero, err := findNativePhaseDispatchCandidates(records, count, 0)
	if err != nil {
		return plan, err
	}
	plan.SelectorOne = selectorOne
	plan.ZeroPreselection = make(
		[]NativePhaseZeroPreselection, 0, len(selectorZero),
	)
	plan.ZeroSecondPass = append(
		[]NativePhaseDispatchCandidate(nil), selectorZero...,
	)
	for _, candidate := range selectorZero {
		if candidate.UnitIndex >= len(scores) {
			return NativePhaseUnitScanPlan{}, fmt.Errorf(
				"fdother: native phase score for unit %d is unavailable",
				candidate.UnitIndex,
			)
		}
		score := scores[candidate.UnitIndex]
		plan.ZeroPreselection = append(
			plan.ZeroPreselection,
			NativePhaseZeroPreselection{
				UnitIndex:   candidate.UnitIndex,
				SelectorArg: 0,
				RunUnitAction: score.SpellCandidateScore53C23 >= 6 ||
					score.ItemCommandScore53C33 >= 6,
			},
		)
	}
	return plan, nil
}
