package battle

import "fmt"

// NativeItemTargetPlan preserves the two 0x14818 calls in 0x1bbdc item
// action case 0.  Field names describe only call roles, not gameplay range,
// item effects, or normalized spell semantics.
type NativeItemTargetPlan struct {
	ItemType           byte
	SelectionMode      int
	SelectionInnerMark int
	EffectMode         int
	TargetCode         int
}

// NativeItemTargetPlanFromRow reads only the item-row bytes consumed by the
// verified 0x1bbdc selector.  The first stage uses +0x10 and +0x15; type 0x17
// alone supplies inner marker 1.  After 0x115b6 confirms one candidate, the
// second stage uses +0x12, inner marker 0, and the same +0x15 target code.
func NativeItemTargetPlanFromRow(row []byte) (NativeItemTargetPlan, error) {
	if len(row) != NativeItemEffectRowSize {
		return NativeItemTargetPlan{}, fmt.Errorf("native item row len=%d want %d", len(row), NativeItemEffectRowSize)
	}
	inner := 0
	if row[0x0d] == 0x17 {
		inner = 1
	}
	return NativeItemTargetPlan{
		ItemType:           row[0x0d],
		SelectionMode:      int(row[0x10]),
		SelectionInnerMark: inner,
		EffectMode:         int(row[0x12]),
		TargetCode:         int(row[0x15]),
	}, nil
}

// NativeItemEffectTargets reproduces the mutation-free target transaction
// around 0x115b6: actor-origin first-stage candidates, confirmed-candidate
// validation, then confirmed-origin final effect targets.  The caller must
// provide a row-derived plan and the original grid flags.
//
// Unlike NativeCommandEffectTargets, TargetCode here is NOT reflected
// through the acting unit's raw camp selector. A selector-relative flip was
// tried on 2026-08-17 (mirroring the proven spell/command fix) and then
// reverted the same day: it broke every real campaign item AI winner
// (ch27-29's itemID 79, TargetCode row+0x15==0, cast by an Enemy-selector
// actor onto an Enemy-camp target -- exactly the same-team heal case
// TargetCode 0's unflipped meaning, camp==Enemy, already matches). The
// item-scoring path (ScoreNativeAI1567E, 0x1567e) does its own selector flip
// on a DIFFERENT row byte (+0x11) for its coarser preselection scan; nothing
// establishes that 0x1bbdc's execution-time TargetCode (+0x15, read here via
// NativeItemTargetPlanFromRow) receives the same selector-relative treatment
// at the disassembly level, and the only production data available says it
// does not. selector is passed through NativeAttackCandidates as a fixed
// no-op (native ABI Own=2) until real evidence says otherwise.
func NativeItemEffectTargets(w, h int, actor, confirmed *Unit, plan NativeItemTargetPlan, flags []byte, units []*Unit) ([]*Unit, error) {
	rawComplete := nativeTargetRosterRawComplete(units)
	if !nativeTargetActorUsable(actor, rawComplete) || !nativeTargetActorUsable(confirmed, rawComplete) {
		return nil, fmt.Errorf("invalid native item actor/confirmed unit")
	}
	const noOpSelector = 2
	selector := noOpSelector
	selection, err := NativeAttackCandidates(
		w, h,
		Cell{X: actor.X, Y: actor.Y},
		plan.SelectionMode, plan.SelectionInnerMark, plan.TargetCode, selector,
		flags, units,
	)
	if err != nil {
		return nil, err
	}
	found := false
	for _, candidate := range selection {
		if candidate == confirmed {
			found = true
			break
		}
	}
	if !found {
		return nil, fmt.Errorf("confirmed unit is not a native item candidate")
	}
	return NativeAttackCandidates(
		w, h,
		Cell{X: confirmed.X, Y: confirmed.Y},
		plan.EffectMode, 0, plan.TargetCode, selector,
		flags, units,
	)
}
