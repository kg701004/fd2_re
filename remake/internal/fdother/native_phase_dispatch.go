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

// NativePhaseUnitScanPlan keeps the three initial-state diagnostic lists
// separate.  It is not executable control flow: the original invokes both
// callback opportunities after every record, may stop on a nonzero pending
// code, and rereads records changed by earlier actions.
type NativePhaseUnitScanPlan struct {
	SelectorOne      []NativePhaseDispatchCandidate
	ZeroPreselection []NativePhaseZeroPreselection
	ZeroSecondPass   []NativePhaseDispatchCandidate
}

// NativePhaseScanPass identifies the three non-interchangeable loops in
// 0x1d80b and 0x1d8ba.  The values are data labels, not gameplay names.
type NativePhaseScanPass byte

const (
	NativePhaseScanSelectorOne NativePhaseScanPass = iota + 1
	NativePhaseScanZeroPreselection
	NativePhaseScanZeroSecondPass
)

const (
	nativeGlobalEventCount  = 90
	nativeChapterEventCount = 30
	nativeNoGlobalEventID   = 0xff
)

// NativePhaseScanCallbacks supplies the side effects that remain outside this
// raw control-flow adapter.  Every callback is required: silently omitting a
// native table call would change the scan's observable order.
//
// RunUnitAction returns the raw [0x51a8f] selector.  The original resets it to
// 0xff before every record; 0xff means no global-event dispatch.  ChapterIndex
// is deliberately read after RunGlobalEvent because the original reloads
// [0x53c03] at that point instead of caching it for the pass.
type NativePhaseScanCallbacks struct {
	Preselect       func(unitIndex int) (NativePhasePreselectionScores, error)
	RunUnitAction   func(unitIndex int, selector byte) (int, error)
	RunGlobalEvent  func(eventID, unitIndex int) error
	ChapterIndex    func() (int, error)
	RunChapterEvent func(chapterIndex, unitIndex int) error
	PendingCode     func() (int, error)
}

// NativePhaseScanResult records where a nonzero [0x53ecc] stopped the scan.
// PendingCode remains raw: this layer does not name code 1 or 2 as a scene,
// victory, town, or shop transition.
type NativePhaseScanResult struct {
	Stopped     bool
	Pass        NativePhaseScanPass
	UnitIndex   int
	PendingCode int
}

func nativePhaseRecordEligible(record []byte, selector byte) bool {
	return record[6] == selector && record[5]&0x81 == 0 && record[0x26] == 0
}

func validateNativePhaseScanCallbacks(callbacks NativePhaseScanCallbacks) error {
	switch {
	case callbacks.Preselect == nil:
		return fmt.Errorf("fdother: native phase preselection callback is unavailable")
	case callbacks.RunUnitAction == nil:
		return fmt.Errorf("fdother: native phase unit-action callback is unavailable")
	case callbacks.RunGlobalEvent == nil:
		return fmt.Errorf("fdother: native phase global-event callback is unavailable")
	case callbacks.ChapterIndex == nil:
		return fmt.Errorf("fdother: native phase chapter-index callback is unavailable")
	case callbacks.RunChapterEvent == nil:
		return fmt.Errorf("fdother: native phase chapter-event callback is unavailable")
	case callbacks.PendingCode == nil:
		return fmt.Errorf("fdother: native phase pending-code callback is unavailable")
	default:
		return nil
	}
}

func runNativePhaseRecordTail(
	callbacks NativePhaseScanCallbacks,
	eventID int,
	pass NativePhaseScanPass,
	unitIndex int,
) (NativePhaseScanResult, error) {
	if eventID != nativeNoGlobalEventID {
		if eventID < 0 || eventID >= nativeGlobalEventCount {
			return NativePhaseScanResult{}, fmt.Errorf(
				"fdother: native global event index %d is outside 0..%d",
				eventID, nativeGlobalEventCount-1,
			)
		}
		if err := callbacks.RunGlobalEvent(eventID, unitIndex); err != nil {
			return NativePhaseScanResult{}, err
		}
	}
	chapterIndex, err := callbacks.ChapterIndex()
	if err != nil {
		return NativePhaseScanResult{}, err
	}
	if chapterIndex < 0 || chapterIndex >= nativeChapterEventCount {
		return NativePhaseScanResult{}, fmt.Errorf(
			"fdother: native chapter event index %d is outside 0..%d",
			chapterIndex, nativeChapterEventCount-1,
		)
	}
	if err := callbacks.RunChapterEvent(chapterIndex, unitIndex); err != nil {
		return NativePhaseScanResult{}, err
	}
	pendingCode, err := callbacks.PendingCode()
	if err != nil {
		return NativePhaseScanResult{}, err
	}
	if pendingCode == 0 {
		return NativePhaseScanResult{}, nil
	}
	return NativePhaseScanResult{
		Stopped:     true,
		Pass:        pass,
		UnitIndex:   unitIndex,
		PendingCode: pendingCode,
	}, nil
}

// ExecuteNativePhaseUnitScans preserves the directly observed control flow of
// 0x1d80b and 0x1d8ba:
//
//   - selector-one pass;
//   - selector-zero preselection pass, with an action only when either signed
//     producer score is at least six;
//   - selector-zero second pass.
//
// Eligibility is reread from records for every pass.  This matters because a
// successful first-pass action may set record+5 bit7 and must then disappear
// from the second pass.  The optional global-event table, mandatory chapter
// table, and pending-code check run after every record, including ineligible
// records.  A nonzero pending code stops only after both table opportunities,
// matching the original ordering.
func ExecuteNativePhaseUnitScans(
	records []byte,
	count int,
	callbacks NativePhaseScanCallbacks,
) (NativePhaseScanResult, error) {
	const stride = 0x50
	if count < 0 {
		return NativePhaseScanResult{}, fmt.Errorf(
			"fdother: negative native phase count %d", count,
		)
	}
	if count > 0 && len(records) < count*stride {
		return NativePhaseScanResult{}, fmt.Errorf(
			"fdother: native phase records have %d bytes, need %d",
			len(records), count*stride,
		)
	}
	if err := validateNativePhaseScanCallbacks(callbacks); err != nil {
		return NativePhaseScanResult{}, err
	}

	passes := [...]struct {
		kind      NativePhaseScanPass
		selector  byte
		preselect bool
	}{
		{NativePhaseScanSelectorOne, 1, false},
		{NativePhaseScanZeroPreselection, 0, true},
		{NativePhaseScanZeroSecondPass, 0, false},
	}
	for _, pass := range passes {
		for unit := 0; unit < count; unit++ {
			eventID := nativeNoGlobalEventID
			record := records[unit*stride : (unit+1)*stride]
			if nativePhaseRecordEligible(record, pass.selector) {
				runAction := true
				if pass.preselect {
					scores, err := callbacks.Preselect(unit)
					if err != nil {
						return NativePhaseScanResult{}, err
					}
					runAction = scores.SpellCandidateScore53C23 >= 6 ||
						scores.ItemCommandScore53C33 >= 6
				}
				if runAction {
					var err error
					eventID, err = callbacks.RunUnitAction(unit, pass.selector)
					if err != nil {
						return NativePhaseScanResult{}, err
					}
				}
			}
			result, err := runNativePhaseRecordTail(
				callbacks, eventID, pass.kind, unit,
			)
			if err != nil || result.Stopped {
				return result, err
			}
		}
	}
	return NativePhaseScanResult{}, nil
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
